from __future__ import annotations

import os
import resource
import shutil
import signal
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional


class PathEscapeError(ValueError):
    """Raised when a write path resolves outside the sandbox scratch dir."""


@dataclass(frozen=True)
class SandboxResult:
    exit_code: Optional[int]
    stdout: str
    stderr: str
    killed: bool
    duration_seconds: float


class Sandbox:
    def __init__(self, *, prefix: str = "agent-sandbox-") -> None:
        self._prefix = prefix
        self._scratch: Optional[Path] = None

    @property
    def scratch_dir(self) -> Path:
        if self._scratch is None:
            raise RuntimeError("Sandbox is not active; use as a context manager")
        return self._scratch

    def __enter__(self) -> "Sandbox":
        self._scratch = Path(tempfile.mkdtemp(prefix=self._prefix))
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        try:
            if self._scratch is not None and self._scratch.exists():
                shutil.rmtree(self._scratch, ignore_errors=True)
        finally:
            self._scratch = None

    def write_file(self, rel_path: str, content: str) -> Path:
        if self._scratch is None:
            raise RuntimeError("Sandbox is not active")
        scratch = self._scratch.resolve()
        candidate = (scratch / rel_path).resolve()
        try:
            candidate.relative_to(scratch)
        except ValueError as e:
            raise PathEscapeError(
                f"refused to write outside sandbox: {rel_path!r} -> {candidate}"
            ) from e
        candidate.parent.mkdir(parents=True, exist_ok=True)
        candidate.write_text(content, encoding="utf-8")
        return candidate

    def run_pytest(
        self,
        *,
        cpu_seconds: int = 10,
        wall_seconds: float = 15.0,
    ) -> SandboxResult:
        if self._scratch is None:
            raise RuntimeError("Sandbox is not active")
        scratch = self._scratch.resolve()

        def _preexec() -> None:
            os.setsid()
            resource.setrlimit(resource.RLIMIT_CPU, (cpu_seconds, cpu_seconds))

        cmd = [
            sys.executable,
            "-m",
            "pytest",
            f"--rootdir={scratch}",
            "-p",
            "no:cacheprovider",
            "-q",
        ]

        proc: Optional[subprocess.Popen] = None
        start = time.monotonic()
        try:
            proc = subprocess.Popen(
                cmd,
                cwd=str(scratch),
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                preexec_fn=_preexec,
                text=True,
            )
            try:
                stdout, stderr = proc.communicate(timeout=wall_seconds)
                duration = time.monotonic() - start
                return SandboxResult(
                    exit_code=proc.returncode,
                    stdout=stdout or "",
                    stderr=stderr or "",
                    killed=False,
                    duration_seconds=duration,
                )
            except subprocess.TimeoutExpired:
                _kill_group(proc.pid)
                try:
                    stdout, stderr = proc.communicate(timeout=2.0)
                except subprocess.TimeoutExpired:
                    stdout, stderr = "", ""
                duration = time.monotonic() - start
                return SandboxResult(
                    exit_code=None,
                    stdout=stdout or "",
                    stderr=(stderr or "") + "\n[sandbox] killed by wall-clock limit",
                    killed=True,
                    duration_seconds=duration,
                )
        finally:
            if proc is not None and proc.poll() is None:
                _kill_group(proc.pid)
                try:
                    proc.wait(timeout=2.0)
                except subprocess.TimeoutExpired:
                    pass


def _kill_group(pid: int) -> None:
    try:
        pgid = os.getpgid(pid)
    except ProcessLookupError:
        return
    try:
        os.killpg(pgid, signal.SIGKILL)
    except ProcessLookupError:
        pass

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

SCHEMA_VERSION = 1
EXCERPT_MAX_BYTES = 4096
TRUNCATION_MARKER = "\n...[truncated]"


@dataclass(frozen=True)
class FailureEntry:
    schema_version: int
    run_id: str
    iteration: int
    timestamp: str
    goal: str
    error_type: str
    root_cause_summary: str
    code_or_assumptions: str
    next_hypothesis: str
    failing_test_excerpt: str

    def to_dict(self) -> dict:
        return asdict(self)


def truncate_excerpt(text: str, max_bytes: int = EXCERPT_MAX_BYTES) -> str:
    if not text:
        return ""
    encoded = text.encode("utf-8")
    if len(encoded) <= max_bytes:
        return text
    marker = TRUNCATION_MARKER
    keep = max_bytes - len(marker.encode("utf-8"))
    if keep <= 0:
        return marker.lstrip("\n")[:max_bytes]
    truncated = encoded[:keep].decode("utf-8", errors="ignore")
    return truncated + marker


def now_utc_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def resolve_persistent_root(env: Optional[dict] = None) -> Path:
    e = env if env is not None else os.environ
    val = e.get("AGENT_MEMORY_DIR")
    if val:
        return Path(val).expanduser()
    return Path.home() / ".agent" / "memory"


def _atomic_write(path: Path, data: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(data)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def _atomic_append_line(path: Path, line: str) -> None:
    """Append a single JSONL line atomically: read existing, write new+line to tmp, rename."""
    path.parent.mkdir(parents=True, exist_ok=True)
    existing = ""
    if path.exists():
        existing = path.read_text(encoding="utf-8")
    tmp = path.with_suffix(path.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        f.write(existing)
        if existing and not existing.endswith("\n"):
            f.write("\n")
        f.write(line)
        if not line.endswith("\n"):
            f.write("\n")
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


class FailureMemoryWriter:
    def __init__(self, persistent_root: Path, workdir: Path, run_id: str):
        self.persistent_root = Path(persistent_root)
        self.workdir = Path(workdir)
        self.run_id = run_id
        self.persistent_paths: list[Path] = []
        self.workdir_paths: list[Path] = []

    @property
    def persistent_jsonl(self) -> Path:
        return self.persistent_root / "failures" / f"{self.run_id}.jsonl"

    def workdir_mirror(self, iteration: int) -> Path:
        return self.workdir / "failures" / f"iter-{iteration}.json"

    def write(self, entry: FailureEntry) -> Path:
        line = json.dumps(entry.to_dict(), sort_keys=True)
        jsonl_path = self.persistent_jsonl
        _atomic_append_line(jsonl_path, line)

        mirror_path = self.workdir_mirror(entry.iteration)
        _atomic_write(mirror_path, json.dumps(entry.to_dict(), indent=2, sort_keys=True) + "\n")

        if jsonl_path not in self.persistent_paths:
            self.persistent_paths.append(jsonl_path)
        self.workdir_paths.append(mirror_path)
        return jsonl_path

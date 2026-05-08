from __future__ import annotations

import json
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Literal, Optional

from agent.failure_memory import REQUIRED_FIELDS as FAILURE_REQUIRED_FIELDS
from agent.failure_memory import resolve_persistent_root
from agent.success_memory import REQUIRED_FIELDS as SUCCESS_REQUIRED_FIELDS

Kind = Literal["failures", "successes", "all"]

GOAL_COL_WIDTH = 60
SUMMARY_COL_WIDTH = 80
ELLIPSIS = "…"


@dataclass(frozen=True)
class Row:
    kind: str
    timestamp: str
    iterations: int
    goal: str
    summary: str
    source_path: str


def _warn(msg: str) -> None:
    print(f"agent memory: warning: {msg}", file=sys.stderr)


def _validate_failure(d: dict) -> None:
    for k in FAILURE_REQUIRED_FIELDS:
        if k not in d:
            raise ValueError(f"missing field: {k}")
    if d["schema_version"] != 1:
        raise ValueError(f"unexpected schema_version: {d['schema_version']!r}")
    if not isinstance(d["iteration"], int):
        raise ValueError("iteration must be int")


def _validate_success(d: dict) -> None:
    for k in SUCCESS_REQUIRED_FIELDS:
        if k not in d:
            raise ValueError(f"missing field: {k}")
    if d["schema_version"] != 1:
        raise ValueError(f"unexpected schema_version: {d['schema_version']!r}")
    if not isinstance(d["iterations"], int):
        raise ValueError("iterations must be int")


def _scan_failures(root: Path) -> Iterable[Row]:
    fdir = root / "failures"
    if not fdir.is_dir():
        return
    for path in sorted(fdir.glob("*.jsonl")):
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as e:
            _warn(f"could not read {path}: {e}")
            continue
        warned = False
        for lineno, line in enumerate(text.splitlines(), start=1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                _validate_failure(d)
            except (ValueError, json.JSONDecodeError) as e:
                if not warned:
                    _warn(f"skipping malformed entry in {path} (line {lineno}): {e}")
                    warned = True
                continue
            summary = f"{d['error_type']}: {d['root_cause_summary']}"
            yield Row(
                kind="failure",
                timestamp=str(d["timestamp"]),
                iterations=int(d["iteration"]),
                goal=str(d["goal"]),
                summary=summary,
                source_path=str(path),
            )


def _scan_successes(root: Path) -> Iterable[Row]:
    sdir = root / "successes"
    if not sdir.is_dir():
        return
    for path in sorted(sdir.glob("*.json")):
        try:
            d = json.loads(path.read_text(encoding="utf-8"))
            _validate_success(d)
        except (ValueError, json.JSONDecodeError, OSError) as e:
            _warn(f"skipping malformed entry in {path}: {e}")
            continue
        iters = int(d["iterations"])
        summary = f"{d['model']} (solved in {iters} iter)"
        yield Row(
            kind="success",
            timestamp=str(d["timestamp"]),
            iterations=iters,
            goal=str(d["goal"]),
            summary=summary,
            source_path=str(path),
        )


def list_entries(
    persistent_root: Optional[Path] = None,
    kind: Kind = "all",
    goal_substring: Optional[str] = None,
    limit: Optional[int] = None,
) -> list[Row]:
    root = Path(persistent_root) if persistent_root else resolve_persistent_root()
    rows: list[Row] = []
    if kind in ("failures", "all"):
        rows.extend(_scan_failures(root))
    if kind in ("successes", "all"):
        rows.extend(_scan_successes(root))
    if goal_substring:
        needle = goal_substring.lower()
        rows = [r for r in rows if needle in r.goal.lower()]
    rows.sort(key=lambda r: r.timestamp, reverse=True)
    if limit is not None:
        rows = rows[:limit]
    return rows


def _truncate(s: str, width: int) -> str:
    if len(s) <= width:
        return s
    if width <= 1:
        return ELLIPSIS[:width]
    return s[: width - 1] + ELLIPSIS


def format_rows(rows: list[Row]) -> str:
    header = f"{'kind':<8}  {'timestamp':<27}  {'iters':>5}  {'goal':<{GOAL_COL_WIDTH}}  summary"
    lines = [header]
    for r in rows:
        goal = _truncate(r.goal, GOAL_COL_WIDTH)
        summary = _truncate(r.summary, SUMMARY_COL_WIDTH)
        lines.append(
            f"{r.kind:<8}  {r.timestamp:<27}  {r.iterations:>5}  {goal:<{GOAL_COL_WIDTH}}  {summary}"
        )
    return "\n".join(lines)


def run_list(
    *,
    kind: Kind = "all",
    goal_substring: Optional[str] = None,
    limit: Optional[int] = None,
    persistent_root: Optional[Path] = None,
    out=None,
) -> int:
    out = out if out is not None else sys.stdout
    rows = list_entries(
        persistent_root=persistent_root,
        kind=kind,
        goal_substring=goal_substring,
        limit=limit,
    )
    if not rows:
        if goal_substring:
            print(f"No memory entries match goal substring {goal_substring!r}.", file=out)
        else:
            print("No memory entries found.", file=out)
        return 0
    print(format_rows(rows), file=out)
    return 0

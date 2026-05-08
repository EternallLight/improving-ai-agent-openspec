from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Optional

from agent.failure_memory import (
    now_utc_iso,
    resolve_persistent_root,
    _atomic_write,
)

SCHEMA_VERSION = 1


@dataclass(frozen=True)
class SuccessEntry:
    schema_version: int
    run_id: str
    timestamp: str
    goal: str
    solution_code: str
    tests: str
    iterations: int
    model: str

    def to_dict(self) -> dict:
        return asdict(self)


REQUIRED_FIELDS = (
    "schema_version",
    "run_id",
    "timestamp",
    "goal",
    "solution_code",
    "tests",
    "iterations",
    "model",
)


class SuccessSchemaError(ValueError):
    pass


def _validate_dict(d: dict) -> None:
    for k in REQUIRED_FIELDS:
        if k not in d:
            raise SuccessSchemaError(f"missing field: {k}")
        v = d[k]
        if v is None or (isinstance(v, str) and v == ""):
            raise SuccessSchemaError(f"field {k} is empty")
    if d["schema_version"] != 1:
        raise SuccessSchemaError(f"unexpected schema_version: {d['schema_version']!r}")
    if not isinstance(d["iterations"], int) or d["iterations"] < 1:
        raise SuccessSchemaError("iterations must be a positive int")


def successes_dir(root: Optional[Path] = None) -> Path:
    r = Path(root) if root else resolve_persistent_root()
    p = r / "successes"
    p.mkdir(parents=True, exist_ok=True)
    return p


def success_path(run_id: str, root: Optional[Path] = None) -> Path:
    return successes_dir(root) / f"{run_id}.json"


def write(
    *,
    run_id: str,
    goal: str,
    solution_code: str,
    tests: str,
    iterations: int,
    model: str,
    root: Optional[Path] = None,
    timestamp: Optional[str] = None,
) -> Path:
    entry = SuccessEntry(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        timestamp=timestamp or now_utc_iso(),
        goal=goal,
        solution_code=solution_code,
        tests=tests,
        iterations=iterations,
        model=model,
    )
    d = entry.to_dict()
    _validate_dict(d)
    path = success_path(run_id, root)
    _atomic_write(path, json.dumps(d, indent=2, sort_keys=True) + "\n")
    return path


def load(path: Path) -> dict:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    _validate_dict(data)
    return data

from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import success_memory
from agent.failure_memory import resolve_persistent_root
from agent.success_memory import SuccessSchemaError


def _common(**overrides):
    base = dict(
        run_id="run-1",
        goal="implement add",
        solution_code="def add(a,b): return a+b",
        tests="from solution import add\ndef test(): assert add(1,2)==3",
        iterations=1,
        model="kimi-k2-0905-preview",
    )
    base.update(overrides)
    return base


def test_write_read_roundtrip(tmp_path):
    path = success_memory.write(root=tmp_path, **_common())
    assert path.exists()
    assert path == tmp_path / "successes" / "run-1.json"
    loaded = success_memory.load(path)
    assert loaded["run_id"] == "run-1"
    assert loaded["schema_version"] == 1
    assert loaded["iterations"] == 1
    assert loaded["goal"] == "implement add"


def test_schema_rejects_empty_fields(tmp_path):
    with pytest.raises(SuccessSchemaError):
        success_memory.write(root=tmp_path, **_common(goal=""))
    with pytest.raises(SuccessSchemaError):
        success_memory.write(root=tmp_path, **_common(solution_code=""))


def test_schema_rejects_bad_iterations(tmp_path):
    with pytest.raises(SuccessSchemaError):
        success_memory.write(root=tmp_path, **_common(iterations=0))


def test_atomic_write_no_tmp_left(tmp_path):
    success_memory.write(root=tmp_path, **_common())
    leftover = list((tmp_path / "successes").glob("*.tmp"))
    assert leftover == []


def test_env_override(tmp_path, monkeypatch):
    custom = tmp_path / "custom_mem"
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(custom))
    # Use module-level resolution
    success_memory.write(**_common())
    assert (custom / "successes" / "run-1.json").exists()


def test_load_validates(tmp_path):
    path = tmp_path / "successes" / "bad.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps({"schema_version": 1, "run_id": "x"}))
    with pytest.raises(SuccessSchemaError):
        success_memory.load(path)

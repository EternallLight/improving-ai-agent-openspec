from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent.failure_memory import (
    EXCERPT_MAX_BYTES,
    FailureEntry,
    FailureMemoryWriter,
    SCHEMA_VERSION,
    now_utc_iso,
    resolve_persistent_root,
    truncate_excerpt,
)


def _entry(iteration: int = 1, **overrides) -> FailureEntry:
    base = dict(
        schema_version=SCHEMA_VERSION,
        run_id="run-x",
        iteration=iteration,
        timestamp=now_utc_iso(),
        goal="implement add",
        error_type="AssertionError",
        root_cause_summary="wrong operator",
        code_or_assumptions="def add(a,b): return a-b",
        next_hypothesis="use +",
        failing_test_excerpt="E   AssertionError",
    )
    base.update(overrides)
    return FailureEntry(**base)


def test_schema_completeness(tmp_path):
    e = _entry()
    d = e.to_dict()
    for k in (
        "schema_version", "run_id", "iteration", "timestamp", "goal",
        "error_type", "root_cause_summary", "code_or_assumptions",
        "next_hypothesis", "failing_test_excerpt",
    ):
        assert k in d and d[k] != ""
    assert d["schema_version"] == 1


def test_jsonl_append_and_mirror(tmp_path):
    persistent = tmp_path / "persist"
    workdir = tmp_path / "work"
    workdir.mkdir()
    w = FailureMemoryWriter(persistent, workdir, run_id="run-x")

    w.write(_entry(iteration=1, root_cause_summary="first"))
    w.write(_entry(iteration=2, root_cause_summary="second"))

    jsonl = persistent / "failures" / "run-x.jsonl"
    assert jsonl.exists()
    lines = jsonl.read_text().strip().splitlines()
    assert len(lines) == 2
    parsed = [json.loads(l) for l in lines]
    assert parsed[0]["root_cause_summary"] == "first"
    assert parsed[1]["iteration"] == 2

    m1 = workdir / "failures" / "iter-1.json"
    m2 = workdir / "failures" / "iter-2.json"
    assert m1.exists() and m2.exists()
    assert json.loads(m1.read_text())["root_cause_summary"] == "first"
    # Pretty-printed mirror
    assert "\n" in m1.read_text()


def test_env_var_override(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "custom"))
    root = resolve_persistent_root()
    assert root == tmp_path / "custom"


def test_default_root(monkeypatch):
    monkeypatch.delenv("AGENT_MEMORY_DIR", raising=False)
    root = resolve_persistent_root()
    assert root == Path.home() / ".agent" / "memory"


def test_atomic_write_no_partial_tmp(tmp_path):
    persistent = tmp_path / "p"
    workdir = tmp_path / "w"
    workdir.mkdir()
    w = FailureMemoryWriter(persistent, workdir, run_id="r")
    w.write(_entry(iteration=1))
    # No leftover .tmp in failures dir
    failures_dir = persistent / "failures"
    leftover = list(failures_dir.glob("*.tmp"))
    assert leftover == []


def test_atomic_write_recovery_on_simulated_interrupt(tmp_path, monkeypatch):
    """If the rename never happens (simulated crash), the JSONL should remain valid (or absent)."""
    persistent = tmp_path / "p"
    workdir = tmp_path / "w"
    workdir.mkdir()
    w = FailureMemoryWriter(persistent, workdir, run_id="r")
    w.write(_entry(iteration=1))

    # Simulate interruption mid-second-write by patching os.replace to fail
    import os as _os
    real_replace = _os.replace
    calls = {"n": 0}

    def boom(src, dst):
        calls["n"] += 1
        if calls["n"] == 1:  # first call is the JSONL rename
            raise RuntimeError("simulated crash")
        return real_replace(src, dst)

    monkeypatch.setattr("agent.failure_memory.os.replace", boom)
    with pytest.raises(RuntimeError):
        w.write(_entry(iteration=2))
    monkeypatch.setattr("agent.failure_memory.os.replace", real_replace)

    # JSONL should still parse: only the original entry visible.
    jsonl = persistent / "failures" / "r.jsonl"
    lines = [l for l in jsonl.read_text().splitlines() if l]
    for line in lines:
        json.loads(line)  # must parse
    assert len(lines) == 1


def test_truncate_excerpt_caps_at_4kb():
    big = "x" * (EXCERPT_MAX_BYTES * 2)
    out = truncate_excerpt(big)
    assert len(out.encode("utf-8")) <= EXCERPT_MAX_BYTES
    assert "[truncated]" in out


def test_truncate_excerpt_passthrough_when_small():
    assert truncate_excerpt("hello") == "hello"
    assert truncate_excerpt("") == ""

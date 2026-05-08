from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path

import pytest

from agent import cli, memory_inspector


def _write_failure_jsonl(root: Path, run_id: str, entries: list[dict]) -> Path:
    p = root / "failures" / f"{run_id}.jsonl"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("\n".join(json.dumps(e, sort_keys=True) for e in entries) + "\n", encoding="utf-8")
    return p


def _write_success_json(root: Path, run_id: str, entry: dict) -> Path:
    p = root / "successes" / f"{run_id}.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return p


def _failure_entry(*, run_id, iteration, timestamp, goal, error_type="AssertionError", root_cause="bad math"):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "iteration": iteration,
        "timestamp": timestamp,
        "goal": goal,
        "error_type": error_type,
        "root_cause_summary": root_cause,
        "code_or_assumptions": "x",
        "next_hypothesis": "y",
        "failing_test_excerpt": "z",
    }


def _success_entry(*, run_id, timestamp, goal, iterations=2, model="kimi"):
    return {
        "schema_version": 1,
        "run_id": run_id,
        "timestamp": timestamp,
        "goal": goal,
        "solution_code": "def f(): pass",
        "tests": "def test_f(): pass",
        "iterations": iterations,
        "model": model,
    }


def _populate(root: Path) -> None:
    _write_failure_jsonl(
        root, "runA",
        [
            _failure_entry(run_id="runA", iteration=1, timestamp="2026-01-01T00:00:00.000000Z", goal="Write add(a,b) function"),
            _failure_entry(run_id="runA", iteration=2, timestamp="2026-01-02T00:00:00.000000Z", goal="Write add(a,b) function"),
        ],
    )
    _write_success_json(
        root, "runB",
        _success_entry(run_id="runB", timestamp="2026-01-03T00:00:00.000000Z", goal="Write multiply function", iterations=3),
    )
    _write_success_json(
        root, "runC",
        _success_entry(run_id="runC", timestamp="2025-12-25T00:00:00.000000Z", goal="Older success goal"),
    )


def test_list_entries_orders_filters_limits(tmp_path):
    _populate(tmp_path)
    rows = memory_inspector.list_entries(persistent_root=tmp_path)
    assert [r.timestamp for r in rows] == sorted([r.timestamp for r in rows], reverse=True)
    assert {r.kind for r in rows} == {"failure", "success"}

    only_fails = memory_inspector.list_entries(persistent_root=tmp_path, kind="failures")
    assert all(r.kind == "failure" for r in only_fails)
    assert len(only_fails) == 2

    only_succ = memory_inspector.list_entries(persistent_root=tmp_path, kind="successes")
    assert all(r.kind == "success" for r in only_succ)
    assert len(only_succ) == 2

    by_goal = memory_inspector.list_entries(persistent_root=tmp_path, goal_substring="ADD")
    assert len(by_goal) == 2
    assert all("add" in r.goal.lower() for r in by_goal)

    limited = memory_inspector.list_entries(persistent_root=tmp_path, limit=2)
    assert len(limited) == 2
    assert limited[0].timestamp == "2026-01-03T00:00:00.000000Z"


def test_malformed_entries_resilient(tmp_path, capsys):
    good = _failure_entry(run_id="runA", iteration=1, timestamp="2026-01-01T00:00:00.000000Z", goal="g1")
    bad_path = tmp_path / "failures" / "runA.jsonl"
    bad_path.parent.mkdir(parents=True, exist_ok=True)
    bad_path.write_text(json.dumps(good, sort_keys=True) + "\n{not json\n", encoding="utf-8")

    succ_dir = tmp_path / "successes"
    succ_dir.mkdir(parents=True, exist_ok=True)
    (succ_dir / "bad.json").write_text("not json", encoding="utf-8")
    _write_success_json(tmp_path, "good", _success_entry(run_id="good", timestamp="2026-02-01T00:00:00.000000Z", goal="ok"))

    rc = memory_inspector.run_list(persistent_root=tmp_path)
    assert rc == 0
    err = capsys.readouterr().err
    assert "runA.jsonl" in err
    assert "bad.json" in err
    rows = memory_inspector.list_entries(persistent_root=tmp_path)
    assert len(rows) == 2


def test_agent_memory_dir_override(tmp_path, monkeypatch, capsys):
    custom = tmp_path / "custom_root"
    custom.mkdir()
    _write_success_json(custom, "x", _success_entry(run_id="x", timestamp="2026-01-01T00:00:00.000000Z", goal="custom-goal"))

    decoy_home = tmp_path / "fake_home"
    decoy_home.mkdir()
    monkeypatch.setenv("HOME", str(decoy_home))
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(custom))

    rc = cli.main(["memory", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "custom-goal" in out


def _hash_tree(root: Path) -> dict[str, tuple[str, float]]:
    out = {}
    for p in sorted(root.rglob("*")):
        if p.is_file():
            data = p.read_bytes()
            out[str(p.relative_to(root))] = (hashlib.sha256(data).hexdigest(), p.stat().st_mtime_ns)
    return out


def test_cli_memory_list_readonly_and_shape(tmp_path, monkeypatch, capsys):
    root = tmp_path / "mem"
    root.mkdir()
    _populate(root)
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(root))

    before = _hash_tree(root)
    rc = cli.main(["memory", "list"])
    out = capsys.readouterr().out
    after = _hash_tree(root)

    assert rc == 0
    assert before == after
    assert out.splitlines()[0].startswith("kind")
    assert "failure" in out
    assert "success" in out


def test_cli_memory_list_empty(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "empty"))
    rc = cli.main(["memory", "list"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "No memory entries" in out


def test_cli_memory_list_invalid_kind(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        cli.main(["memory", "list", "--kind", "bogus"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "bogus" in err or "invalid" in err.lower()


def test_cli_memory_list_invalid_limit(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path))
    with pytest.raises(SystemExit) as exc:
        cli.main(["memory", "list", "--limit", "0"])
    assert exc.value.code != 0


def test_cli_memory_no_run_dir_created(tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "mem"))
    monkeypatch.chdir(tmp_path)
    rc = cli.main(["memory", "list"])
    assert rc == 0
    assert not (tmp_path / ".agent-runs").exists()


def test_cli_help_mentions_memory_list(capsys):
    with pytest.raises(SystemExit):
        cli.main(["--help"])
    out = capsys.readouterr().out
    assert "memory list" in out


def test_truncation_and_alignment(tmp_path):
    long_goal = "g" * 200
    _write_failure_jsonl(
        tmp_path, "r",
        [_failure_entry(run_id="r", iteration=1, timestamp="2026-01-01T00:00:00.000000Z", goal=long_goal,
                        error_type="E", root_cause="x" * 200)],
    )
    rows = memory_inspector.list_entries(persistent_root=tmp_path)
    formatted = memory_inspector.format_rows(rows)
    data_line = formatted.splitlines()[1]
    assert "…" in data_line
    assert long_goal not in data_line

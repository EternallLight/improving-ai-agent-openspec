from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import memory_retrieval, success_memory
from agent.failure_memory import (
    FailureEntry,
    FailureMemoryWriter,
    SCHEMA_VERSION,
    now_utc_iso,
)


def _write_failure(root: Path, run_id: str, goal: str, summary: str, hyp: str, ts: str | None = None):
    workdir = root / "_wd" / run_id
    workdir.mkdir(parents=True, exist_ok=True)
    w = FailureMemoryWriter(root, workdir, run_id=run_id)
    w.write(
        FailureEntry(
            schema_version=SCHEMA_VERSION,
            run_id=run_id,
            iteration=1,
            timestamp=ts or now_utc_iso(),
            goal=goal,
            error_type="AssertionError",
            root_cause_summary=summary,
            code_or_assumptions="x",
            next_hypothesis=hyp,
            failing_test_excerpt="E   AssertionError",
        )
    )


def _write_success(root: Path, run_id: str, goal: str, ts: str | None = None):
    success_memory.write(
        root=root,
        run_id=run_id,
        goal=goal,
        solution_code="def x(): pass",
        tests="def test(): pass",
        iterations=1,
        model="kimi",
        timestamp=ts,
    )


def test_empty_corpus(tmp_path):
    res = memory_retrieval.retrieve("anything", tmp_path)
    assert res.failures == []
    assert res.successes == []


def test_retrieves_relevant_failure(tmp_path):
    _write_failure(tmp_path, "r1", "implement add function", "wrong operator", "use +")
    _write_failure(tmp_path, "r2", "parse JSON file from disk", "missing import", "import json")
    res = memory_retrieval.retrieve("implement add", tmp_path)
    assert len(res.failures) >= 1
    assert res.failures[0].run_id == "r1"


def test_threshold_drops_unrelated(tmp_path):
    _write_failure(tmp_path, "r1", "completely unrelated topic about birds", "x", "y")
    res = memory_retrieval.retrieve("compute fibonacci sequence", tmp_path, threshold=0.9)
    assert res.failures == []


def test_reproducibility(tmp_path):
    _write_failure(tmp_path, "r1", "add numbers", "wrong op", "use +")
    _write_failure(tmp_path, "r2", "add integers", "off by one", "fix bound")
    a = memory_retrieval.retrieve("add", tmp_path)
    b = memory_retrieval.retrieve("add", tmp_path)
    assert [(r.run_id, r.score) for r in a.failures] == [(r.run_id, r.score) for r in b.failures]


def test_tie_break_timestamp_then_runid(tmp_path):
    # Identical text → identical scores. Newer timestamp wins; then run_id asc.
    _write_failure(tmp_path, "ra", "foo bar baz", "rcs", "hyp", ts="2026-01-01T00:00:00.000000Z")
    _write_failure(tmp_path, "rb", "foo bar baz", "rcs", "hyp", ts="2026-02-01T00:00:00.000000Z")
    _write_failure(tmp_path, "rc", "foo bar baz", "rcs", "hyp", ts="2026-02-01T00:00:00.000000Z")
    res = memory_retrieval.retrieve("foo bar baz", tmp_path, k_failures=3)
    ids = [r.run_id for r in res.failures]
    # Newer timestamps first; among rb/rc tie, rb < rc lexicographically
    assert ids[0] in ("rb",)
    assert ids[1] in ("rc",)
    assert ids[2] == "ra"


def test_malformed_jsonl_skipped(tmp_path):
    failures_dir = tmp_path / "failures"
    failures_dir.mkdir(parents=True)
    f = failures_dir / "mixed.jsonl"
    good = json.dumps(
        {
            "schema_version": 1,
            "run_id": "good",
            "iteration": 1,
            "timestamp": now_utc_iso(),
            "goal": "implement add",
            "error_type": "X",
            "root_cause_summary": "rcs",
            "code_or_assumptions": "y",
            "next_hypothesis": "z",
            "failing_test_excerpt": "E",
        }
    )
    f.write_text("not json\n" + good + "\n{\"missing\": true}\n")
    res = memory_retrieval.retrieve("implement add", tmp_path)
    assert len(res.failures) == 1
    assert res.failures[0].run_id == "good"


def test_successes_retrieved(tmp_path):
    _write_success(tmp_path, "s1", "implement multiplication")
    _write_success(tmp_path, "s2", "completely unrelated bird study")
    res = memory_retrieval.retrieve("implement multiplication", tmp_path)
    assert len(res.successes) >= 1
    assert res.successes[0].run_id == "s1"


def test_k_env_overrides(tmp_path, monkeypatch):
    for i in range(5):
        _write_failure(tmp_path, f"r{i}", "shared topic word", "rcs", "hyp")
    monkeypatch.setenv("AGENT_RETRIEVAL_K_FAILURES", "1")
    res = memory_retrieval.retrieve("shared topic word", tmp_path)
    assert len(res.failures) == 1


def test_ref_payload_loadable(tmp_path):
    _write_failure(tmp_path, "r1", "implement add", "rcs", "hyp")
    res = memory_retrieval.retrieve("implement add", tmp_path)
    ref = res.failures[0]
    assert Path(ref.path).exists()
    assert ref.payload["run_id"] == "r1"

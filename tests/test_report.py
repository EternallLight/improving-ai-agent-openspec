from __future__ import annotations

import json

import pytest

from agent.llm.client import TokenUsage
from agent.report import RunReport, write_report


def _make_report(**overrides) -> RunReport:
    defaults = dict(
        goal="write add(a,b)",
        outcome="success",
        iterations=1,
        tokens=TokenUsage(prompt=10, completion=20, total=30),
        model="kimi-k2-0905-preview",
        artifacts={"workdir": "/tmp/x", "run_report": "/tmp/x/run-report.json"},
        started_at="2026-05-08T00:00:00.000000Z",
        finished_at="2026-05-08T00:00:01.000000Z",
        success_entry="/tmp/x/successes/r.json",
    )
    defaults.update(overrides)
    return RunReport(**defaults)


def test_report_requires_all_fields():
    with pytest.raises(ValueError):
        _make_report(goal="")
    with pytest.raises(ValueError):
        _make_report(model="")
    with pytest.raises(ValueError):
        _make_report(artifacts={})
    with pytest.raises(ValueError):
        _make_report(artifacts={"workdir": "/tmp/x"})
    with pytest.raises(ValueError):
        _make_report(started_at="")
    with pytest.raises(ValueError):
        _make_report(iterations=0)


def test_report_token_total_consistency():
    with pytest.raises(ValueError):
        TokenUsage(prompt=1, completion=2, total=99)


def test_write_report_roundtrip(tmp_path):
    report = _make_report(
        artifacts={
            "workdir": str(tmp_path),
            "run_report": str(tmp_path / "run-report.json"),
        }
    )
    path = write_report(report, tmp_path)
    assert path.exists()
    data = json.loads(path.read_text())
    assert data["goal"] == "write add(a,b)"
    assert data["tokens"]["total"] == 30
    assert data["iterations"] == 1

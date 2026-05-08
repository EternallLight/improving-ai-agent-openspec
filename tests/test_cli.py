from __future__ import annotations

import json

import pytest

from agent import cli
from tests.fakes import FakeLLMClient


def test_cli_success_with_fake_client(tmp_path, capsys):
    fake = FakeLLMClient(content="hello world", prompt_tokens=4, completion_tokens=6, model="fake-kimi")

    def factory(model):
        return fake, model or "fake-kimi"

    rc = cli.main(
        ["write add(a,b)", "--workdir", str(tmp_path)],
        client_factory=factory,
    )
    assert rc == 0
    report_path = tmp_path / "run-report.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text())
    assert data["goal"] == "write add(a,b)"
    assert data["outcome"] == "success"
    assert data["iterations"] == 1
    assert data["model"] == "fake-kimi"
    assert data["tokens"] == {"prompt": 4, "completion": 6, "total": 10}
    for key in ("workdir", "run_report", "llm_response"):
        assert key in data["artifacts"] and data["artifacts"][key]
    # All artifact paths exist on disk
    from pathlib import Path

    assert Path(data["artifacts"]["llm_response"]).read_text() == "hello world"
    assert data["started_at"] and data["finished_at"]


def test_cli_missing_api_key(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    rc = cli.main(["any goal", "--workdir", str(tmp_path)])
    assert rc != 0
    err = capsys.readouterr().err
    assert "MOONSHOT_API_KEY" in err
    report_path = tmp_path / "run-report.json"
    assert report_path.exists()
    data = json.loads(report_path.read_text())
    assert data["outcome"] == "failure"


def test_cli_missing_goal_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0

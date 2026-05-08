from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import cli
from agent.sandbox import SandboxResult
from tests.fakes import FakeLLMClient

GOOD_RESPONSE = """```python
# solution.py
def add(a, b):
    return a + b
```

```python
# test_solution.py
from solution import add

def test_add():
    assert add(1, 2) == 3
```
"""


class _FakeSandbox:
    def __init__(self, results):
        self._results = list(results)

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def write_file(self, rel_path, content):
        return Path("/tmp/fake") / rel_path

    def run_pytest(self, **kwargs):
        return self._results.pop(0)


def _ok():
    return SandboxResult(exit_code=0, stdout="ok", stderr="", killed=False, duration_seconds=0.1)


def _fail():
    return SandboxResult(exit_code=1, stdout="", stderr="bad", killed=False, duration_seconds=0.1)


def test_cli_success_with_fake_client(tmp_path):
    fake = FakeLLMClient(content=GOOD_RESPONSE, prompt_tokens=4, completion_tokens=6, model="fake-kimi")

    def client_factory(model):
        return fake, model or "fake-kimi"

    def sandbox_factory():
        return _FakeSandbox([_ok()])

    rc = cli.main(
        ["write add(a,b)", "--workdir", str(tmp_path), "--max-iterations", "3"],
        client_factory=client_factory,
        sandbox_factory=sandbox_factory,
    )
    assert rc == 0
    data = json.loads((tmp_path / "run-report.json").read_text())
    assert data["outcome"] == "success"
    assert data["iterations"] == 1
    assert data["max_iterations"] == 3
    assert data["tokens"] == {"prompt": 4, "completion": 6, "total": 10}
    assert data["iteration_log"][0]["outcome"] == "success"
    for k in ("workdir", "run_report"):
        assert data["artifacts"][k]


def test_cli_gave_up_exits_nonzero_with_stderr(tmp_path, capsys):
    fake = FakeLLMClient(content=GOOD_RESPONSE, model="fake")
    results = [_fail(), _fail()]

    def client_factory(model):
        return fake, model or "fake"

    def sandbox_factory():
        return _FakeSandbox([results.pop(0)])

    rc = cli.main(
        ["impossible", "--workdir", str(tmp_path), "--max-iterations", "2"],
        client_factory=client_factory,
        sandbox_factory=sandbox_factory,
    )
    assert rc != 0
    err = capsys.readouterr().err
    assert "gave up after 2 iterations" in err
    data = json.loads((tmp_path / "run-report.json").read_text())
    assert data["outcome"] == "gave_up"
    assert data["iterations"] == 2
    assert len(data["iteration_log"]) == 2


def test_cli_invalid_max_iterations_zero(tmp_path, capsys):
    with pytest.raises(SystemExit) as exc:
        cli.main(["x", "--workdir", str(tmp_path), "--max-iterations", "0"])
    assert exc.value.code != 0
    err = capsys.readouterr().err
    assert "max-iterations" in err or ">= 1" in err


def test_cli_missing_api_key(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    rc = cli.main(["any goal", "--workdir", str(tmp_path)])
    assert rc != 0
    data = json.loads((tmp_path / "run-report.json").read_text())
    assert data["outcome"] == "failure"


def test_cli_missing_goal_exits_nonzero(tmp_path):
    with pytest.raises(SystemExit) as exc:
        cli.main([])
    assert exc.value.code != 0

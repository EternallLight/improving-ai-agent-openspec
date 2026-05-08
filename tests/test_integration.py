"""Integration tests for PRD acceptance criteria T1, T2, T4, T5, T9.

These exercise the real Sandbox (subprocess + pytest) but mock the LLM with
canned responses so the tests are deterministic and offline.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from agent import cli, solve_loop
from agent.sandbox import Sandbox
from tests.fakes import FakeLLMClient


GOOD_ADD = """```python
# solution.py
def add(a, b):
    return a + b
```

```python
# test_solution.py
from solution import add

def test_add():
    assert add(2, 3) == 5
```
"""

BUGGY_THEN_FIXED_FIRST = """```python
# solution.py
def add(a, b):
    return a - b
```

```python
# test_solution.py
from solution import add

def test_add():
    assert add(2, 3) == 5
```
"""

ALWAYS_BROKEN = """```python
# solution.py
def add(a, b):
    raise RuntimeError("nope")
```

```python
# test_solution.py
from solution import add

def test_add():
    assert add(1, 1) == 2
```
"""

ESCAPE_ATTEMPT = """```python
# ../escape.py
def add(a, b):
    return a + b
```

```python
# test_solution.py
def test_x():
    assert True
```
"""

INFINITE_LOOP = """```python
# solution.py
def go():
    while True:
        pass
```

```python
# test_solution.py
from solution import go

def test_loop():
    go()
"""


def test_T1_trivial_task_one_iteration(tmp_path):
    fake = FakeLLMClient(content=GOOD_ADD, model="fake")
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3, wall_seconds=15.0),
        llm_client=fake,
        workdir=tmp_path,
    )
    assert result.outcome == "success"
    assert result.iterations == 1


def test_T2_nontrivial_multiple_iterations(tmp_path):
    fake = FakeLLMClient(
        responses=[BUGGY_THEN_FIXED_FIRST, "operator was wrong, use +", GOOD_ADD],
        model="fake",
    )
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=4, wall_seconds=15.0),
        llm_client=fake,
        workdir=tmp_path,
    )
    assert result.outcome == "success"
    assert result.iterations == 2
    iter2_messages = fake.calls[2]["messages"]
    user = next(m for m in iter2_messages if m["role"] == "user")
    assert "Iteration 1" in user["content"]


def test_T4_sandbox_blocks_escape(tmp_path):
    from agent.sandbox import PathEscapeError

    with Sandbox() as sb:
        with pytest.raises(PathEscapeError):
            sb.write_file("../escape.py", "x = 1")
        with pytest.raises(PathEscapeError):
            sb.write_file("/etc/agent_pwn", "x = 1")


def test_T4_sandbox_kills_runaway(tmp_path):
    fake = FakeLLMClient(content=INFINITE_LOOP, model="fake")
    result = solve_loop.run(
        goal="x",
        config=solve_loop.SolveConfig(max_iterations=1, cpu_seconds=2, wall_seconds=3.0),
        llm_client=fake,
        workdir=tmp_path,
    )
    assert result.outcome == "gave_up"
    assert result.iterations == 1
    assert result.iteration_log[0].outcome in ("sandbox_killed", "failure")


def test_T5_circuit_breaker_clean_giveup(tmp_path, capsys):
    fake = FakeLLMClient(content=ALWAYS_BROKEN, model="fake")

    def client_factory(model):
        return fake, "fake"

    rc = cli.main(
        ["fail forever", "--workdir", str(tmp_path), "--max-iterations", "2"],
        client_factory=client_factory,
    )
    assert rc != 0
    err = capsys.readouterr().err
    assert "gave up after 2 iterations" in err
    data = json.loads((tmp_path / "run-report.json").read_text())
    assert data["outcome"] == "gave_up"
    assert data["iterations"] == 2
    assert data["max_iterations"] == 2


def test_T9_run_report_complete_for_all_outcomes(tmp_path):
    # Success
    success_dir = tmp_path / "success"
    fake = FakeLLMClient(content=GOOD_ADD, model="fake")
    rc = cli.main(
        ["x", "--workdir", str(success_dir), "--max-iterations", "2"],
        client_factory=lambda m: (fake, "fake"),
    )
    assert rc == 0
    _assert_complete(json.loads((success_dir / "run-report.json").read_text()))

    # Gave up
    gave_dir = tmp_path / "gave"
    fake2 = FakeLLMClient(content=ALWAYS_BROKEN, model="fake")
    rc = cli.main(
        ["x", "--workdir", str(gave_dir), "--max-iterations", "1"],
        client_factory=lambda m: (fake2, "fake"),
    )
    assert rc != 0
    _assert_complete(json.loads((gave_dir / "run-report.json").read_text()))

    # Failure (exception path)
    fail_dir = tmp_path / "fail"

    def boom_factory(model):
        raise RuntimeError("boom")

    rc = cli.main(
        ["x", "--workdir", str(fail_dir)],
        client_factory=boom_factory,
    )
    assert rc != 0
    data = json.loads((fail_dir / "run-report.json").read_text())
    # Exception path: minimal but every required field present
    for k in ("goal", "outcome", "iterations", "max_iterations", "model", "tokens", "started_at", "finished_at", "artifacts"):
        assert k in data and data[k] not in (None, "", "unknown")


def _assert_complete(data: dict) -> None:
    for k in ("goal", "outcome", "iterations", "max_iterations", "model", "tokens", "started_at", "finished_at", "artifacts", "iteration_log"):
        assert k in data, f"missing {k}"
        assert data[k] not in (None, "", "unknown"), f"{k} is empty/unknown"
    assert data["tokens"]["total"] == data["tokens"]["prompt"] + data["tokens"]["completion"]
    if data["iteration_log"]:
        sum_total = sum(e["tokens"]["total"] for e in data["iteration_log"])
        assert sum_total == data["tokens"]["total"]
        for e in data["iteration_log"]:
            for path in e["artifacts"].values():
                assert Path(path).exists(), f"artifact missing: {path}"
    for path in data["artifacts"].values():
        if path.startswith("/"):
            assert Path(path).exists() or path.endswith("run-report.json")

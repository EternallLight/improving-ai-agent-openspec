"""Phase 4 acceptance scenarios T3 (cross-run improvement) and T7 (success reuse).

Both use canned LLM responses; the second run benefits from prior-run context
injected at iteration 1.
"""
from __future__ import annotations

import json
from pathlib import Path

from agent import solve_loop
from agent.sandbox import SandboxResult
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
    assert add(1, 2) == 3
```
"""

BAD_ADD = """```python
# solution.py
def add(a, b):
    return a - b
```

```python
# test_solution.py
from solution import add

def test_add():
    assert add(1, 2) == 3
```
"""

REFLECT = '```json\n{"error_type":"AssertionError","root_cause_summary":"used minus","code_or_assumptions":"return a-b","next_hypothesis":"use plus"}\n```'


class FakeSandbox:
    def __init__(self, results):
        self._results = list(results)
        self._idx = 0

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def scratch_dir(self):
        return Path("/tmp/fake")

    def write_file(self, rel, content):
        return Path("/tmp/fake") / rel

    def run_pytest(self, **kw):
        r = self._results[min(self._idx, len(self._results) - 1)]
        self._idx += 1
        return r


def _ok():
    return SandboxResult(exit_code=0, stdout="", stderr="", killed=False, duration_seconds=0.1)


def _fail():
    return SandboxResult(exit_code=1, stdout="", stderr="AssertionError", killed=False, duration_seconds=0.1)


def test_T3_cross_run_failure_reuse(tmp_path, monkeypatch):
    """First run fails (gives up). Second run uses retrieved prior failure and succeeds in fewer iterations."""
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "mem"))

    # Run 1: 3 bad attempts, gave_up at cap=3
    fake1 = FakeLLMClient(
        responses=[BAD_ADD, REFLECT, BAD_ADD, REFLECT, BAD_ADD, REFLECT]
    )
    sandboxes1 = [FakeSandbox([_fail()]) for _ in range(3)]
    result1 = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake1,
        workdir=tmp_path / "run1",
        sandbox_factory=lambda: sandboxes1.pop(0),
        run_id="run1",
    )
    assert result1.outcome == "gave_up"
    assert result1.iterations == 3

    # Run 2: same goal, succeeds on first try (model would benefit from prior failure)
    fake2 = FakeLLMClient(responses=[GOOD_ADD])
    sandboxes2 = [FakeSandbox([_ok()])]
    result2 = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake2,
        workdir=tmp_path / "run2",
        sandbox_factory=lambda: sandboxes2.pop(0),
        run_id="run2",
    )
    assert result2.outcome == "success"
    assert result2.iterations <= result1.iterations
    assert len(result2.retrieved_failures) >= 1
    assert any(r["run_id"] == "run1" for r in result2.retrieved_failures)


def test_T7_success_reuse(tmp_path, monkeypatch):
    """First run succeeds. Second near-identical run also succeeds in <= iterations."""
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "mem"))

    fake1 = FakeLLMClient(responses=[GOOD_ADD])
    sandboxes1 = [FakeSandbox([_ok()])]
    result1 = solve_loop.run(
        goal="implement add(a,b)",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake1,
        workdir=tmp_path / "run1",
        sandbox_factory=lambda: sandboxes1.pop(0),
        run_id="r1",
    )
    assert result1.outcome == "success"

    fake2 = FakeLLMClient(responses=[GOOD_ADD])
    sandboxes2 = [FakeSandbox([_ok()])]
    result2 = solve_loop.run(
        goal="implement add(a,b)",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake2,
        workdir=tmp_path / "run2",
        sandbox_factory=lambda: sandboxes2.pop(0),
        run_id="r2",
    )
    assert result2.outcome == "success"
    assert result2.iterations <= result1.iterations
    assert len(result2.retrieved_successes) >= 1
    assert any(r["run_id"] == "r1" for r in result2.retrieved_successes)

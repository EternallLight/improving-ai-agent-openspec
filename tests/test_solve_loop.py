from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest

from agent import solve_loop
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

BAD_THEN_GOOD_FIRST = """```python
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


class FakeSandbox:
    def __init__(self, results: list[SandboxResult]):
        self._results = list(results)
        self._idx = 0
        self.writes: list[tuple[str, str]] = []

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    @property
    def scratch_dir(self) -> Path:
        return Path("/tmp/fake")

    def write_file(self, rel_path, content):
        self.writes.append((rel_path, content))
        return Path("/tmp/fake") / rel_path

    def run_pytest(self, **kwargs) -> SandboxResult:
        r = self._results[min(self._idx, len(self._results) - 1)]
        self._idx += 1
        return r


def _ok() -> SandboxResult:
    return SandboxResult(exit_code=0, stdout="passed", stderr="", killed=False, duration_seconds=0.1)


def _fail() -> SandboxResult:
    return SandboxResult(exit_code=1, stdout="", stderr="AssertionError", killed=False, duration_seconds=0.1)


def test_success_first_iter_writes_no_failures_dir(tmp_path):
    fake = FakeLLMClient(responses=[GOOD_RESPONSE])
    sandboxes = [FakeSandbox([_ok()])]
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.outcome == "success"
    assert result.failure_persistent_paths == []
    assert result.failure_workdir_paths == []
    assert not (tmp_path / "failures").exists()


def test_k_failed_iters_yield_k_jsonl_lines_and_k_mirrors(tmp_path, monkeypatch):
    import json
    persistent = tmp_path / "mem"
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(persistent))
    fake = FakeLLMClient(
        responses=[
            BAD_THEN_GOOD_FIRST,
            '```json\n{"error_type":"AssertionError","root_cause_summary":"wrong op","code_or_assumptions":"return a-b","next_hypothesis":"use +"}\n```',
            BAD_THEN_GOOD_FIRST,
            '```json\n{"error_type":"AssertionError","root_cause_summary":"still wrong","code_or_assumptions":"return a-b","next_hypothesis":"use +"}\n```',
        ]
    )
    sandboxes = [FakeSandbox([_fail()]), FakeSandbox([_fail()])]
    result = solve_loop.run(
        goal="g",
        config=solve_loop.SolveConfig(max_iterations=2),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.outcome == "gave_up"
    assert len(result.failure_workdir_paths) == 2
    assert len(result.failure_persistent_paths) == 1
    jsonl = Path(result.failure_persistent_paths[0])
    lines = [l for l in jsonl.read_text().splitlines() if l]
    assert len(lines) == 2
    parsed = [json.loads(l) for l in lines]
    assert parsed[0]["iteration"] == 1
    assert parsed[1]["iteration"] == 2
    assert parsed[0]["error_type"] == "AssertionError"
    for mp in result.failure_workdir_paths:
        assert Path(mp).exists()


def test_trivial_succeeds_in_one_iteration(tmp_path):
    fake = FakeLLMClient(responses=[GOOD_RESPONSE])
    sandboxes = [FakeSandbox([_ok()])]

    def factory():
        return sandboxes.pop(0)

    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=factory,
    )
    assert result.outcome == "success"
    assert result.iterations == 1
    assert len(result.iteration_log) == 1
    assert result.iteration_log[0].outcome == "success"
    assert (tmp_path / "iter-1" / "code.py").exists()


def test_fail_then_succeed_passes_reflection_forward(tmp_path):
    # First iteration: parsable but tests fail. Then reflection call. Then second iteration: success.
    # Our loop calls LLM 1 time per iteration for generate, plus 1 reflect call on failure.
    fake = FakeLLMClient(
        responses=[
            BAD_THEN_GOOD_FIRST,            # iter 1 generate
            "the bug is wrong operator",    # iter 1 reflect
            GOOD_RESPONSE,                  # iter 2 generate
        ]
    )
    sandboxes = [FakeSandbox([_fail()]), FakeSandbox([_ok()])]

    def factory():
        return sandboxes.pop(0)

    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=factory,
    )
    assert result.outcome == "success"
    assert result.iterations == 2
    # The third call (iter 2 generate) should have included the reflection in its prompt.
    iter2_messages = fake.calls[2]["messages"]
    user_msg = next(m for m in iter2_messages if m["role"] == "user")
    assert "Iteration 1" in user_msg["content"]
    assert "wrong operator" in user_msg["content"]


def test_impossible_gives_up_at_cap(tmp_path):
    fake = FakeLLMClient(content=GOOD_RESPONSE)  # always returns same parsable response
    sandboxes = [FakeSandbox([_fail()]) for _ in range(10)]

    def factory():
        return sandboxes.pop(0)

    result = solve_loop.run(
        goal="impossible",
        config=solve_loop.SolveConfig(max_iterations=2),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=factory,
    )
    assert result.outcome == "gave_up"
    assert result.iterations == 2
    assert len(result.iteration_log) == 2
    assert all(e.outcome == "failure" for e in result.iteration_log)


def test_parse_failure_is_recoverable(tmp_path):
    fake = FakeLLMClient(
        responses=[
            "no code here at all",  # iter 1 generate (unparsable)
            GOOD_RESPONSE,          # iter 2 generate (good)
        ]
    )
    sandboxes = [FakeSandbox([_ok()])]

    def factory():
        return sandboxes.pop(0)

    result = solve_loop.run(
        goal="x",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=factory,
    )
    assert result.outcome == "success"
    assert result.iterations == 2
    assert result.iteration_log[0].outcome == "failure"


def test_token_aggregation(tmp_path):
    fake = FakeLLMClient(responses=[GOOD_RESPONSE], prompt_tokens=4, completion_tokens=6)
    sandboxes = [FakeSandbox([_ok()])]
    result = solve_loop.run(
        goal="x",
        config=solve_loop.SolveConfig(max_iterations=2),
        llm_client=fake,
        workdir=tmp_path,
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.tokens.total == 10
    assert result.tokens.total == sum(e.tokens.total for e in result.iteration_log)

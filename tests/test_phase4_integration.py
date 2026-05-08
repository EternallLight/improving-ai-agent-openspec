from __future__ import annotations

import json
from pathlib import Path

from agent import solve_loop, success_memory
from agent.failure_memory import (
    FailureEntry,
    FailureMemoryWriter,
    SCHEMA_VERSION,
    now_utc_iso,
)
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

BAD_RESPONSE = """```python
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
    return SandboxResult(exit_code=0, stdout="ok", stderr="", killed=False, duration_seconds=0.1)


def _fail():
    return SandboxResult(exit_code=1, stdout="", stderr="AssertionError", killed=False, duration_seconds=0.1)


def test_empty_corpus_prompt_unchanged(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "mem"))
    fake = FakeLLMClient(responses=[GOOD_RESPONSE])
    sandboxes = [FakeSandbox([_ok()])]
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=2),
        llm_client=fake,
        workdir=tmp_path / "work",
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.outcome == "success"
    user_msg = next(m for m in fake.calls[0]["messages"] if m["role"] == "user")
    assert "Prior-run context" not in user_msg["content"]
    assert user_msg["content"].startswith("Goal: implement add")


def test_populated_corpus_injects_block(tmp_path, monkeypatch):
    mem = tmp_path / "mem"
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(mem))
    # Pre-populate failure and success
    wd = tmp_path / "_pre"
    wd.mkdir()
    FailureMemoryWriter(mem, wd, run_id="prior-fail").write(
        FailureEntry(
            schema_version=SCHEMA_VERSION,
            run_id="prior-fail",
            iteration=1,
            timestamp=now_utc_iso(),
            goal="implement add function",
            error_type="AssertionError",
            root_cause_summary="used minus instead of plus",
            code_or_assumptions="def add(a,b): return a-b",
            next_hypothesis="use + operator",
            failing_test_excerpt="E AssertionError",
        )
    )
    success_memory.write(
        root=mem,
        run_id="prior-success",
        goal="implement add",
        solution_code="def add(a,b):\n    return a + b",
        tests="def test(): pass",
        iterations=1,
        model="kimi",
    )

    fake = FakeLLMClient(responses=[GOOD_RESPONSE])
    sandboxes = [FakeSandbox([_ok()])]
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=2),
        llm_client=fake,
        workdir=tmp_path / "work",
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.outcome == "success"
    user_msg = next(m for m in fake.calls[0]["messages"] if m["role"] == "user")
    assert "Prior-run context" in user_msg["content"]
    assert "Prior failures on similar goals" in user_msg["content"]
    assert "Prior successful solutions on similar goals" in user_msg["content"]
    assert "use + operator" in user_msg["content"]
    # retrieved_context surfaced on result
    assert len(result.retrieved_failures) >= 1
    assert len(result.retrieved_successes) >= 1
    for entry in result.retrieved_failures + result.retrieved_successes:
        assert Path(entry["path"]).exists()
    # success_entry written and points to existing file
    assert result.success_entry_path
    assert Path(result.success_entry_path).exists()


def test_no_retrieval_on_iter2(tmp_path, monkeypatch):
    mem = tmp_path / "mem"
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(mem))
    wd = tmp_path / "_pre"
    wd.mkdir()
    FailureMemoryWriter(mem, wd, run_id="prior-fail").write(
        FailureEntry(
            schema_version=SCHEMA_VERSION,
            run_id="prior-fail",
            iteration=1,
            timestamp=now_utc_iso(),
            goal="implement add",
            error_type="X",
            root_cause_summary="rcs",
            code_or_assumptions="x",
            next_hypothesis="hyp",
            failing_test_excerpt="E",
        )
    )

    fake = FakeLLMClient(
        responses=[
            BAD_RESPONSE,
            '```json\n{"error_type":"X","root_cause_summary":"r","code_or_assumptions":"x","next_hypothesis":"y"}\n```',
            GOOD_RESPONSE,
        ]
    )
    sandboxes = [FakeSandbox([_fail()]), FakeSandbox([_ok()])]
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=3),
        llm_client=fake,
        workdir=tmp_path / "work",
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.outcome == "success"
    iter1_user = next(m for m in fake.calls[0]["messages"] if m["role"] == "user")
    iter2_user = next(m for m in fake.calls[2]["messages"] if m["role"] == "user")
    assert "Prior-run context" in iter1_user["content"]
    assert "Prior-run context" not in iter2_user["content"]


def test_failure_run_writes_no_success(tmp_path, monkeypatch):
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "mem"))
    fake = FakeLLMClient(content=BAD_RESPONSE)
    sandboxes = [FakeSandbox([_fail()]) for _ in range(5)]
    result = solve_loop.run(
        goal="implement add",
        config=solve_loop.SolveConfig(max_iterations=2),
        llm_client=fake,
        workdir=tmp_path / "work",
        sandbox_factory=lambda: sandboxes.pop(0),
    )
    assert result.outcome == "gave_up"
    assert result.success_entry_path is None
    assert not (tmp_path / "mem" / "successes").exists() or list((tmp_path / "mem" / "successes").iterdir()) == []

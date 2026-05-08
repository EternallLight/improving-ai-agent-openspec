from __future__ import annotations

from agent.reflection import Reflection

GENERATE_SYSTEM = """You are a careful Python coding agent. Given a goal, produce:
1. A solution module (`solution.py`) that implements the goal.
2. A pytest test module (`test_solution.py`) that imports from `solution` and verifies the goal.

Return your answer as exactly two fenced Python code blocks, in this order:

```python
# solution.py
<code>
```

```python
# test_solution.py
<tests>
```

Do not include any other code blocks. Tests must be runnable with `pytest` and must import from `solution`."""

REFLECT_SYSTEM = """You are reviewing a failing pytest run. Produce a short root-cause summary (2-4 sentences) explaining what went wrong and what the next attempt should change. Do not write code."""


def build_generate_prompt(goal: str, reflections: list[Reflection]) -> list[dict]:
    user_parts: list[str] = [f"Goal: {goal}"]
    if reflections:
        user_parts.append("\nPrior failed attempts (most recent last):")
        for r in reflections:
            user_parts.append(_format_reflection(r))
        user_parts.append(
            "\nProduce a corrected solution.py and test_solution.py that addresses the prior failures."
        )
    return [
        {"role": "system", "content": GENERATE_SYSTEM},
        {"role": "user", "content": "\n".join(user_parts)},
    ]


def build_reflect_prompt(
    goal: str,
    code: str,
    tests: str,
    pytest_output: str,
) -> list[dict]:
    user = f"""Goal: {goal}

solution.py:
```python
{code}
```

test_solution.py:
```python
{tests}
```

Pytest output (truncated):
```
{pytest_output}
```

Summarize the root cause of the failure in 2-4 sentences."""
    return [
        {"role": "system", "content": REFLECT_SYSTEM},
        {"role": "user", "content": user},
    ]


def _format_reflection(r: Reflection) -> str:
    return (
        f"\n--- Iteration {r.iteration} ---\n"
        f"pytest_exit_code: {r.pytest_exit_code}\n"
        f"summary: {r.summary}\n"
        f"stderr_tail:\n{r.stderr_tail}\n"
        f"stdout_tail:\n{r.stdout_tail}\n"
    )

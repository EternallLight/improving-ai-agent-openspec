# PRD — Self-Improving Coding Agent (dogfood project)

A small autonomous agent that takes a coding task as a natural-language goal, writes Python code to solve it, runs the tests, learns from failures, and tries again until it succeeds or gives up. The "self-improving" part means it remembers past failures across runs and uses that memory to avoid repeating mistakes on similar tasks later.

This PRD is framework-neutral. It will be fed independently into OpenSpec and Spec Kit so each can produce its own spec, plan, and implementation. The point of the comparison is to see how each framework handles the same brief.

## Goal

A user runs the agent with a goal like *"write a function that returns the nth Fibonacci number, with tests"* and the agent produces working, tested code without further human input. If it fails, it tries again. If it has seen a similar task before, it starts smarter.

## Required Features

### F1. Goal intake
Accept a coding task as a natural-language string from the CLI. Optionally accept a working directory where the agent should produce its output.

### F2. Iterative solve loop
For each task, the agent runs a generate → test → reflect cycle until either tests pass or a configurable iteration limit is reached. Each iteration produces a code attempt and an evaluation of that attempt.

### F3. Sandboxed test execution
Run generated code in an isolated environment with a CPU/time limit and a writable scratch directory. The sandbox must prevent the generated code from touching the rest of the user's filesystem or running indefinitely.

### F4. Failure reflection
After a failed iteration, capture what failed: the error type, a short root-cause summary, the specific code lines or assumptions involved, and the agent's hypothesis for what to try next.

### F5. Persistent failure memory
Failures captured in F4 persist across runs. The next time a task is run, the agent retrieves the most relevant past failures (by similarity to the new goal) and includes them in its starting context so it doesn't repeat known mistakes.

### F6. Persistent success memory
When a task succeeds, store the goal and the working solution so future similar tasks can reference proven patterns.

### F7. Circuit breaker
The loop terminates cleanly when the iteration limit is hit. The agent reports the failure with its last attempt, its accumulated reflections, and a clear "gave up after N iterations" status. No infinite loops, no zombie processes.

### F8. Run report
At the end of every run (success or fail), the agent prints a summary: goal, iterations used, final outcome, total LLM token cost, and where the produced artifacts (code, tests, memory updates) live on disk.

### F9. Inspectable memory
The user can list what's in failure memory and success memory from the CLI — see what the agent has learned, in human-readable form.

## Out of Scope

- Multi-language support (Python only)
- Multi-file project generation (single-file solutions only)
- Web UI, dashboard, or IDE integration
- Multi-agent / specialist subagent orchestration
- Distributed or cloud execution
- Production-grade Docker isolation (a process-level sandbox is sufficient)
- Authentication, multi-user support, or remote API
- Streaming output of intermediate iterations to the user (final report only is fine)

## How to Test

Each feature has a concrete acceptance test. The test suite for the agent itself should cover these scenarios.

### T1 — Trivial task succeeds in one iteration
Give the agent a task it should solve immediately (e.g. *"write `add(a, b)` that returns a+b, with a passing test"*). **Pass criteria:** exits with success, iteration count = 1, produced file imports and tests pass.

### T2 — Non-trivial task succeeds within the loop
Give the agent a task that's likely to fail at least once (e.g. *"write a function that flattens a deeply nested list, with edge case tests for empty lists and non-list values"*). **Pass criteria:** exits with success, iteration count > 1, produced tests pass.

### T3 — Self-improvement across runs (the core proof point)
Run a task that's known to fail in a specific way the first time. After it eventually succeeds, run a *similar but distinct* task in a fresh process. **Pass criteria:** the second run's starting context includes the relevant past failure (verifiable in the run report or memory inspector), AND the second run uses fewer iterations than the first did for the same kind of failure.

### T4 — Circuit breaker on impossible task
Give the agent an impossible or contradictory goal (e.g. *"write a function that returns the largest prime number"*). **Pass criteria:** exits cleanly with a "gave up after N iterations" status, no hung process, no orphaned sandbox state.

### T5 — Sandbox containment
Give the agent a task whose hidden test attempts to write outside the sandbox or run indefinitely. **Pass criteria:** the sandbox blocks the escape and surfaces it as a failure; nothing is written outside the scratch directory; the time-limited code is killed within the configured limit.

### T6 — Failure capture quality
After T2, inspect the failure memory. **Pass criteria:** entries are structured (not raw stack traces), each entry has a goal, an error type, a root-cause summary, and a hypothesis. A human reading the entry should understand what went wrong without re-running anything.

### T7 — Success pattern reuse
Run a task. After success, run a near-identical task. **Pass criteria:** the second run retrieves and references the first run's stored solution; second run is faster (fewer iterations or skipped reflection).

### T8 — Memory inspector
Run the inspector command after several runs. **Pass criteria:** lists failures and successes in a human-readable form, with goals, outcomes, and timestamps. The user can tell at a glance what the agent has learned.

### T9 — Run report completeness
After any run (T1–T8), check the final report. **Pass criteria:** report contains the goal, iteration count, outcome, token cost, and paths to all produced artifacts. No required field is empty or "unknown."

## Notes for the Build

- Both framework runs will start from this same PRD with no edits. The framework is responsible for asking the right clarifying questions (or making sensible defaults) to turn this into a spec, a plan, and code.
- The acceptance tests above are the contract. A run is "complete" when all nine pass.
- The LLM provider is **Moonshot (Kimi)** only. Do not add Anthropic, OpenAI, or any other provider — this is a hard constraint to keep demo costs on a single existing API key. The provider abstraction can still be clean (a single `LLMClient` interface), but the only implementation is Moonshot.
- Authenticate via the `MOONSHOT_API_KEY` environment variable against Moonshot's OpenAI-compatible endpoint (`https://api.moonshot.ai/v1`).
- Default model: Kimi's flagship coding-tier model (e.g. `kimi-k2` or the current latest). A smaller/cheaper Kimi model may be used for non-reasoning calls (similarity lookups, memory inspection formatting) but generate/reflect must use the flagship — weaker models fail more iterations and cost more in total.
- Token cost reporting in F8 should be expressed in Moonshot tokens / pricing.

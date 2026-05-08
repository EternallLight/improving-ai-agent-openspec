## Why

Phase 1 ships a single-shot CLI that calls Moonshot once and emits a run report. The agent cannot actually solve coding tasks: it has no iteration, no test feedback, and no isolation for the code it generates. Phase 2 turns the CLI into a real agent by adding a generate → test → reflect loop running inside a process-level sandbox, with a circuit breaker that bounds runaway runs.

## What Changes

- Add a solve loop that, on each iteration, generates code + pytest tests via the LLM, executes them in a sandbox, and on failure produces an in-memory reflection that feeds the next iteration.
- Add a process-level sandbox that confines code execution to a writable scratch directory with CPU/wall-time limits and kills runaway processes.
- Add a circuit breaker that terminates the loop at a configurable iteration cap with a clean "gave up after N iterations" outcome.
- Extend the run report so `iterations` reflects the real loop count and `outcome` distinguishes `success`, `failure`, and `gave_up`.
- Extend the CLI with an iteration-cap flag (e.g. `--max-iterations`) and surface the chosen value in the run report.
- Reflections and per-iteration state are in-memory only this phase; structured failure persistence lands in Phase 3.

## Capabilities

### New Capabilities
- `solve-loop`: generate → test → reflect iteration with success/failure/gave-up termination, in-memory reflection passed to the next iteration.
- `sandbox`: process-level execution sandbox with a writable scratch dir, CPU/wall-time limits, filesystem-escape prevention, and guaranteed cleanup of processes and scratch dirs.
- `circuit-breaker`: bounded iteration cap that terminates the loop cleanly when exceeded.

### Modified Capabilities
- `run-report`: `iterations` now reflects real loop count; `outcome` adds a `gave_up` value; report cites per-iteration artifacts (generated code, test output) and the iteration cap in effect.
- `cli`: adds `--max-iterations` flag (with default) surfaced into the run.

## Impact

- New modules under `src/agent/` for the loop, sandbox, and circuit breaker.
- Existing single-call flow becomes the body of iteration 1; the CLI entry point now drives the loop instead of calling the LLM directly.
- New runtime dependency on `pytest` for executing generated tests inside the sandbox; depends on POSIX `resource` limits and process groups (macOS/Linux only this phase).
- Run report JSON schema gains fields; downstream readers must tolerate `outcome=gave_up` and a list of per-iteration entries.

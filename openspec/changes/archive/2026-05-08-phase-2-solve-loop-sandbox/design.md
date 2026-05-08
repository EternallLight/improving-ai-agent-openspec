## Context

Phase 1 produced a working CLI, an `LLMClient` interface with a Moonshot implementation, and a run report. The agent makes one Moonshot call per invocation; there is no execution of generated code, no feedback loop, and no isolation. PRD acceptance tests T1, T2, T4, T5, T9 require the agent to actually solve single-file Python tasks by iterating against test results, give up cleanly when stuck, and never let generated code escape its scratch directory or run forever.

Constraints carried from the PRD: provider is Moonshot only; the flagship Kimi model handles generate and reflect; the loop runs locally on the developer's macOS/Linux box; no Docker dependency.

## Goals / Non-Goals

**Goals:**
- A generate → test → reflect loop that solves single-file Python tasks end-to-end.
- A process-level sandbox with CPU/wall-time limits, a writable scratch dir, and guaranteed cleanup.
- A circuit breaker that produces a clean `gave_up` outcome at the iteration cap.
- Run report carries iteration count, per-iteration artifacts, and the new outcome value.

**Non-Goals:**
- Persisted structured failure entries (Phase 3).
- Cross-run memory or similarity retrieval (Phase 4).
- Memory inspector CLI (Phase 5).
- Multi-file project generation, dependency installation per task, or non-Python tasks.
- Container-level isolation (Docker, gVisor, Firejail). The sandbox is process-level.

## Decisions

### Decision: Loop control lives in a dedicated `solve_loop` module, not inside the CLI

The CLI's `main` becomes a thin wrapper that builds dependencies (LLM client, sandbox factory, config) and hands off to `solve_loop.run(goal, config) -> RunResult`. Iteration state, reflection accumulation, and termination logic stay in one place and are unit-testable without spawning the CLI.

Alternatives considered: keeping the loop inline in `cli.main` (rejected — couples CLI parsing with iteration logic and blocks unit tests); a class hierarchy with strategy objects per phase (rejected — premature; we have one strategy).

### Decision: Sandbox uses `subprocess` + POSIX `resource` limits + a per-run temp dir

Each iteration runs `pytest` in a child process. We use `subprocess.Popen` with `preexec_fn` setting `RLIMIT_CPU` and `RLIMIT_AS`, set the child into its own process group via `os.setsid`, and wait with a wall-clock timeout. On timeout we `os.killpg(pgid, SIGKILL)`. Working directory is a fresh `tempfile.mkdtemp()` per iteration, deleted in a `finally` regardless of outcome.

Filesystem-escape prevention is enforced by (a) writing only the scratch dir as `cwd`, (b) refusing to write any path the model emits that resolves outside the scratch dir after `Path.resolve()`, and (c) never executing the model's output as a shell string — only as files we wrote.

Alternatives considered: Docker (rejected — heavy dependency, slow startup, complicates dev setup); `firejail`/`bubblewrap` (rejected — Linux-only, not portable to the user's Mac); `seccomp` filters (rejected — out of scope for Phase 2; process-level limits are sufficient for the PRD's "kill runaway code" criterion).

Trade-off accepted: a determined adversarial model could still call `os.fork` repeatedly or read files outside the scratch dir. PRD threat model is buggy code, not adversarial code, so this is acceptable.

### Decision: Reflection is in-memory, structured but ephemeral

After a failed iteration, the loop builds a `Reflection` dataclass capturing: iteration index, generated-code snippet, pytest exit code, captured stdout/stderr (truncated), and a short LLM-produced root-cause summary. It is appended to a list passed into the next iteration's prompt. Nothing is written to disk this phase — Phase 3 owns persistence and will reuse the same dataclass shape.

Alternatives considered: writing to disk now and "upgrading" the format in Phase 3 (rejected — Phase 3 is the place to lock the on-disk contract; doing it here forces a rewrite when retrieval lands).

### Decision: Circuit breaker is iteration-count based, not wall-clock

`max_iterations` (default 5, overridable via `--max-iterations`) caps the loop. When exceeded, the loop returns `RunResult(outcome="gave_up", iterations=N, ...)` and the CLI exits non-zero with a single-line stderr message. Each iteration also has its own wall-clock cap (sandbox-level), so the total run is implicitly bounded.

Alternatives considered: total-wall-clock budget (rejected — harder to reason about with variable LLM latency); cost-budget (rejected — Phase 2 doesn't need it; cost is reported, not enforced).

### Decision: Run report grows backward-compatibly

The existing top-level fields stay. We add `iterations` (already present, now meaningful), change `outcome`'s value set to include `gave_up`, and add `iteration_log: [{index, outcome, tokens, artifacts}]`. `tokens` at the top level becomes the sum across iterations.

## Risks / Trade-offs

- **[Risk] `RLIMIT_CPU` and process-group kill don't behave identically on macOS vs Linux** → Mitigation: integration test in CI on both; the `gave_up` path treats sandbox kill as a normal terminal state, not an error.
- **[Risk] LLM emits paths outside the scratch dir or imports that pull in network I/O** → Mitigation: post-resolve path check rejects escapes; document that network I/O is not blocked at the kernel level this phase (process-level sandbox only).
- **[Risk] pytest in the scratch dir picks up the host's `conftest.py` from a parent dir** → Mitigation: invoke pytest with `--rootdir=<scratch>` and `-p no:cacheprovider`; scratch dir is under `tempfile.gettempdir()`, not under the project tree.
- **[Trade-off] In-memory reflections mean a long run loses its reflection trail on crash** → Acceptable; Phase 3 makes them durable. Run report still records per-iteration outcomes so the user knows what happened.
- **[Risk] Model occasionally returns code in a fenced block with prose around it** → Mitigation: a small extractor pulls the largest Python code block and the largest test block; if extraction fails, that iteration counts as a failure with reflection "could not parse model output".

## Open Questions

- Should `max_iterations` default to 5 or 10? PRD does not pin a number. Defaulting to 5 for now; revisit after running the PRD's non-trivial task.
- Should the sandbox kill on memory limit (`RLIMIT_AS`) or just CPU/wall-clock? Starting with both; if `RLIMIT_AS` proves flaky on macOS we'll drop it and rely on wall-clock.

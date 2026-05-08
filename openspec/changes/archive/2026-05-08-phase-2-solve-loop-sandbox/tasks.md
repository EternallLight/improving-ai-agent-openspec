## 1. Sandbox

- [x] 1.1 Add `agent/sandbox.py` with a `Sandbox` class that creates a fresh scratch dir under `tempfile.gettempdir()` and exposes a context-managed lifecycle (enter creates dir, exit cleans up)
- [x] 1.2 Implement `Sandbox.write_file(rel_path, content)` that resolves `rel_path` against the scratch dir and rejects any path that resolves outside it
- [x] 1.3 Implement `Sandbox.run_pytest(cpu_seconds, wall_seconds) -> SandboxResult` using `subprocess.Popen` with `preexec_fn` setting `RLIMIT_CPU` and `os.setsid`, and a wall-clock `wait()`; on timeout `os.killpg(pgid, SIGKILL)` and reap
- [x] 1.4 Pass `--rootdir=<scratch>` and `-p no:cacheprovider` to pytest so host conftests cannot leak in
- [x] 1.5 Ensure scratch dir and any spawned process group are cleaned up in a `finally`, even on exception
- [x] 1.6 Unit-test sandbox: filesystem escape rejected; infinite-loop test killed within wall-clock limit; no orphan processes after run

## 2. Solve loop

- [x] 2.1 Add `agent/reflection.py` with a `Reflection` dataclass: `iteration`, `code_excerpt`, `pytest_exit_code`, `stdout_tail`, `stderr_tail`, `summary`
- [x] 2.2 Add `agent/prompting.py` with two prompt builders: `build_generate_prompt(goal, reflections)` and `build_reflect_prompt(goal, code, tests, pytest_output)`
- [x] 2.3 Add `agent/extract.py`: parse a model response into `(code: str, tests: str)`; if extraction fails, return a typed error so the iteration can be recorded as a parse failure
- [x] 2.4 Add `agent/solve_loop.py` exposing `run(goal, config, llm_client, sandbox_factory) -> RunResult` that loops generate → write files → sandbox-run pytest → reflect-on-failure
- [x] 2.5 Loop termination: success when pytest exit code is 0; `gave_up` when `len(iterations) == max_iterations`; recover-and-continue on parse failure or sandbox kill
- [x] 2.6 Unit-test loop: trivial goal succeeds in 1 iteration (LLM mocked); a fail-then-succeed scenario records 2 iterations and passes the first reflection into the second prompt; impossible goal returns `gave_up` after `max_iterations`

## 3. Circuit breaker & CLI wiring

- [x] 3.1 Add `--max-iterations N` to the CLI argument parser with a documented default and validation (positive int)
- [x] 3.2 Rewrite `cli.main` to construct dependencies and call `solve_loop.run(...)` instead of making a one-shot LLM call
- [x] 3.3 Map `RunResult.outcome` to exit codes: `success` → 0; `failure` and `gave_up` → non-zero; print a single-line stderr message of the form "gave up after N iterations" on `gave_up`
- [x] 3.4 Unit-test CLI: invalid `--max-iterations 0` exits non-zero with stderr message; `gave_up` exit prints expected stderr line and writes the report

## 4. Run report

- [x] 4.1 Extend the run-report data model with `max_iterations` and `iteration_log: list[IterationEntry]` (`index`, `outcome`, `tokens`, `artifacts`)
- [x] 4.2 Aggregate top-level `tokens` as the sum of per-iteration tokens; include `gave_up` as a valid `outcome` value
- [x] 4.3 Persist per-iteration artifacts to `<workdir>/iter-<N>/` (code.py, test_code.py, pytest.stdout, pytest.stderr) and reference those paths from `iteration_log[i].artifacts`
- [x] 4.4 Update the human-readable stdout report to print iteration count, outcome, and per-iteration one-line summaries
- [x] 4.5 Tests: report fields complete on success, failure, and gave-up; cited artifact paths exist; `tokens.total` equals sum across iterations and equals prompt + completion

## 5. Integration & PRD acceptance

- [x] 5.1 Integration test T1 (trivial task): a tiny goal completes in 1 iteration with `outcome=success`
- [x] 5.2 Integration test T2 (non-trivial): a goal that fails the obvious first attempt completes in >1 iteration with reflections passed forward
- [x] 5.3 Integration test T4 (sandbox): malicious-pattern goal cannot escape scratch dir; runaway-loop goal is killed within the wall-clock cap
- [x] 5.4 Integration test T5 (circuit breaker): impossible goal returns `gave_up` at the cap with a clean exit and complete report
- [x] 5.5 Integration test T9 (run report): every required field is populated for all three outcomes; no "unknown" or empty values
- [x] 5.6 README/usage docs updated for `--max-iterations` and the new outcome values

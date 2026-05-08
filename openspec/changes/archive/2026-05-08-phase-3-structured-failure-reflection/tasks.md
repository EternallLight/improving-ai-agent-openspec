## 1. Failure-memory module

- [x] 1.1 Add `agent/failure_memory.py` with a `FailureEntry` dataclass matching the v1 schema and a `truncate_excerpt` helper (4 KB cap with marker)
- [x] 1.2 Implement `FailureMemoryWriter(persistent_root, workdir, run_id)` with `write(entry) -> Path` performing atomic write (`*.tmp` + rename) for both the JSONL append and the per-iteration workdir mirror
- [x] 1.3 Resolve persistent root from `AGENT_MEMORY_DIR` env var with default `~/.agent/memory`; create `failures/` subdirectory on first write
- [x] 1.4 Add `tests/test_failure_memory.py`: schema completeness, JSONL append, workdir mirror, env-var override, atomic-write recovery (simulate interruption), 4 KB truncation

## 2. Reflection extension

- [x] 2.1 Update reflection prompt in `agent/prompting.py` (or wherever the reflect prompt lives) to ask for a JSON block with `error_type`, `root_cause_summary`, `code_or_assumptions`, `next_hypothesis`
- [x] 2.2 Extend `agent/reflection.py` to parse that JSON block; on parse failure, emit a fallback structure with `error_type = "ParseError"` and the raw output as `root_cause_summary`
- [x] 2.3 Update existing reflection tests and add coverage for the parse-failure fallback

## 3. Solve-loop integration

- [x] 3.1 In `agent/solve_loop.py`, instantiate `FailureMemoryWriter` once per run (using the run id and workdir already in scope)
- [x] 3.2 After each failed iteration's reflection is produced, build a `FailureEntry` and call `writer.write(entry)` BEFORE starting the next iteration
- [x] 3.3 Ensure circuit-breaker termination still flushes all entries (verify by test)
- [x] 3.4 Update `tests/test_solve_loop.py` to assert: K failed iterations → K JSONL lines and K workdir mirror files; success-on-first-iter → no `failures/` dir created

## 4. Run report changes

- [x] 4.1 Add `failure_entries: {count, persistent_paths, workdir_paths}` to the report structure in `agent/report.py`
- [x] 4.2 Populate the field from the writer's recorded paths at end-of-run
- [x] 4.3 Update human-readable stdout rendering to include the failure-entry count and persistent path
- [x] 4.4 Update `tests/test_cli.py` and `tests/test_integration.py` to assert the new field is present, paths exist, and counts match the iteration log

## 5. Spec sync

- [x] 5.1 Update `openspec/specs/solve-loop/spec.md` Purpose section if still TBD
- [x] 5.2 Run `openspec validate phase-3-structured-failure-reflection` and resolve any issues
- [x] 5.3 Run the full test suite and confirm all Phase 2 tests still pass alongside new Phase 3 tests

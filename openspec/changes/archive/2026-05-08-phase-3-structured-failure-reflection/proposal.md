## Why

Phase 2 keeps reflections in-memory only, so once a run ends all failure context disappears. Phase 3 (PRD F4) requires every failed iteration to write a structured, human-readable failure entry to disk so a person can understand what went wrong from the entry alone, and so Phase 4 has a real corpus to retrieve from. This phase locks the structured-capture contract before similarity logic layers on.

## What Changes

- Add a `failure-memory` capability that writes one structured entry per failed iteration to a stable on-disk location (JSONL or one file per entry) under the run's workdir, mirrored into a persistent store path (e.g. `~/.agent/memory/failures/`).
- Each entry contains at minimum: `goal`, `error_type`, `root_cause_summary`, `code_or_assumptions` (specific lines/assumptions involved), `next_hypothesis`, plus metadata (`run_id`, `iteration`, `timestamp`).
- Modify the solve loop so that every failed iteration produces a structured failure entry (extending the existing in-memory reflection) and persists it via the failure-memory writer before the next iteration starts. The current-run loop still consumes entries from memory to feed the next iteration's prompt.
- Extend the run report to include the count of persisted failure entries and their paths.
- No retrieval, no cross-run injection, no success memory — write-only this phase.

## Capabilities

### New Capabilities
- `failure-memory`: structured, append-only, write-only persistence of per-iteration failure entries with a stable schema and on-disk format.

### Modified Capabilities
- `solve-loop`: each failed iteration MUST produce a structured failure entry conforming to the failure-memory schema and persist it before the next iteration begins; the in-memory-only constraint is relaxed to allow writes through the failure-memory capability.
- `run-report`: report MUST include the number of persisted failure entries and the path(s) where they were written.

## Impact

- New module `agent/failure_memory.py` (writer + schema).
- Changes to `agent/solve_loop.py` and `agent/reflection.py` to emit structured entries and call the writer.
- Changes to `agent/report.py` to surface failure-entry count and paths.
- New tests under `tests/test_failure_memory.py` and updates to `tests/test_solve_loop.py` / `tests/test_integration.py`.
- New on-disk artifacts under the run workdir and a persistent memory directory; no schema migration since this is the first persisted format.

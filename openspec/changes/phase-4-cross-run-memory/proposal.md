## Why

Phase 3 made the agent capture structured failure entries to disk, but those entries only feed the *current* run. The agent does not actually self-improve across runs: a near-identical goal tomorrow starts from zero. Phase 4 closes that loop by retrieving relevant past failures and successes by similarity at run start and injecting them into the agent's starting context, and by persisting the goal + working solution on every success. This is the PRD's self-improvement proof point (T3, T7).

## What Changes

- Add a persistent **success memory** store: on every successful run, persist `{goal, solution_code, tests, run_id, timestamp, iterations, model}` as one JSON file per success under `<persistent_root>/successes/`.
- Add a **similarity retrieval** layer over both the existing failure-memory JSONL corpus and the new success-memory store. Retrieval runs at the start of every solve loop, scored against the new run's goal, returning top-K failures and top-K successes.
- Inject retrieved entries into the **solve loop's starting prompt** as a clearly-labeled "prior-run context" block (failures with their `next_hypothesis`, successes with their `goal` + solution snippet).
- Extend the **run report** with a `retrieved_context` section listing the entry IDs/paths actually injected, plus `success_entry` (path) when the run succeeds.
- Provider constraint: similarity may use a smaller Kimi model for embeddings/scoring; flagship Kimi remains for generate/reflect.
- Out of scope: the inspector CLI (Phase 5).

## Capabilities

### New Capabilities
- `success-memory`: persistent per-success store of goal + working solution with a stable v1 schema, atomic writes, and an `AGENT_MEMORY_DIR` override.
- `memory-retrieval`: similarity-based retrieval over failure-memory and success-memory at run start, returning top-K of each scored against the new goal, with deterministic tie-breaking.

### Modified Capabilities
- `solve-loop`: starting context for iteration 1 SHALL include retrieved prior-run failures and successes when any are returned by `memory-retrieval`.
- `run-report`: SHALL include a `retrieved_context` field (lists of failure and success entry references actually injected) and, on success, a `success_entry` field pointing to the persisted success file.

## Impact

- New module(s) for success-memory persistence and retrieval (mirrors the shape of `failure-memory`).
- Solve-loop prompt assembly gains a "prior-run context" section before the goal.
- Run-report schema gains two fields; downstream consumers (T9 completeness check) must accept them.
- Adds one extra Moonshot call per run for similarity scoring (smaller model). No new external dependencies; embeddings or lexical scoring both acceptable, decided in design.md.
- Memory layout under `<persistent_root>` extends from `failures/` to also include `successes/`; existing failure JSONL files are untouched.

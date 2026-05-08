## Context

Phase 3 produced a stable, append-only `failure-memory` capability writing v1 JSONL entries to `<persistent_root>/failures/<run_id>.jsonl` (default `~/.agent/memory`, override via `AGENT_MEMORY_DIR`) plus per-iteration workdir mirrors. The solve loop already feeds in-run reflections forward but ignores anything from prior runs. Phase 4 must (a) capture successes the same way, (b) retrieve relevant prior failures and successes by similarity to the new goal, and (c) inject the retrieved context into iteration 1 of the solve loop without breaking existing run-report invariants.

Provider constraint is unchanged: Moonshot (Kimi) only, flagship for generate/reflect, smaller Kimi model permitted for similarity scoring.

## Goals / Non-Goals

**Goals:**
- Persist one success entry per successful run, schema-stable and atomic, mirroring the failure-memory storage shape.
- Retrieve top-K relevant prior failures and successes for a new goal, deterministically, before iteration 1 runs.
- Inject retrieved context into the solve-loop prompt and surface what was injected in the run report.
- Make T3 (cross-run improvement) and T7 (success reuse) verifiable from the run report alone.

**Non-Goals:**
- Inspector CLI (Phase 5).
- Forgetting / pruning / compaction of memory.
- Online learning, fine-tuning, or vector DB infrastructure.
- Modifying any existing failure-memory v1 schema or file layout.

## Decisions

### 1. Success-memory storage: one JSON file per success
- **Decision:** `<persistent_root>/successes/<run_id>.json`, written atomically (write `.tmp`, fsync, rename). One file per success; no JSONL.
- **Why:** Successes are rarer than failure iterations, and the full solution payload is large. Per-file storage keeps reads cheap and avoids rewriting a growing JSONL. Mirrors failure-memory's `AGENT_MEMORY_DIR` semantics so behavior is uniform.
- **Alternative considered:** Append-only `successes.jsonl`. Rejected — payloads include code/tests, JSONL lines become unwieldy and harder to inspect.

### 2. Success entry v1 schema
Fields, all required and non-empty: `schema_version` (=1), `run_id`, `timestamp` (ISO-8601 UTC), `goal`, `solution_code` (string), `tests` (string), `iterations` (int), `model` (string). Mirrors the failure-entry schema discipline so retrieval and inspector code can treat both stores symmetrically.

### 3. Similarity: lexical TF-IDF cosine, no embeddings call
- **Decision:** Build an in-process TF-IDF index over `goal` (and for failures, `goal + root_cause_summary + next_hypothesis`) at retrieval time. Score the new goal against each entry by cosine similarity. Top-K with deterministic tie-break by `timestamp` desc, then `run_id` asc.
- **Why:** Phase 4 must run with Moonshot only and minimal new infrastructure. Lexical scoring is deterministic, cheap, testable, and sufficient to demonstrate T3/T7 on near-identical goals. No embedding storage migration problem if we later swap in a Kimi-based scorer.
- **Alternative considered:** Smaller-Kimi-model scoring per (new_goal, candidate). Rejected for now — adds N provider calls per run-start and nondeterminism. The provider constraint *permits* this; the design *defers* it. Retrieval interface is abstract so we can swap implementations without changing solve-loop or specs.

### 4. K values
- `top_k_failures = 3`, `top_k_successes = 2` by default. Configurable via env (`AGENT_RETRIEVAL_K_FAILURES`, `AGENT_RETRIEVAL_K_SUCCESSES`). Below a minimum cosine threshold (default `0.1`), entries are dropped — better to inject nothing than noise.

### 5. Prompt injection shape
Iteration 1 prompt gains a clearly-labeled prior-run context block placed *before* the goal, with two subsections: "Prior failures on similar goals" (each entry rendered as `goal`, `error_type`, `root_cause_summary`, `next_hypothesis`) and "Prior successful solutions on similar goals" (each entry rendered as `goal` + a bounded code excerpt, max 2 KB per entry). If both lists are empty after threshold filtering, the block is omitted entirely so trivial first-runs are unchanged.

### 6. Run-report extension
Add `retrieved_context: { failures: [{path, run_id, score}], successes: [{path, run_id, score}] }` (always present, possibly empty arrays) and `success_entry: <path>` (present only when `outcome == "success"`, else null). Existing fields and invariants from the run-report spec are untouched.

### 7. Failure-memory spec is *not* modified
Phase 4 only *reads* the failure JSONL corpus. The failure-memory v1 schema, paths, and atomicity guarantees stay frozen. Retrieval is layered on top, not into, that capability.

## Risks / Trade-offs

- **Lexical-only similarity misses semantically similar but lexically distant goals** → Acceptable for Phase 4 acceptance tests (T3, T7 use near-identical goals). The retrieval interface is abstracted so Phase 5+ can swap in a model-based scorer without re-specifying solve-loop or run-report.
- **Injected context could mislead the model on superficially-similar but actually-different goals** → Threshold filter (default 0.1) plus small K (3+2) plus the model's own judgment. Failures injected carry `next_hypothesis`, not a forced fix.
- **Memory grows unbounded** → Out of scope this phase. Files are small JSON; even thousands of entries are fine. Pruning becomes a Phase 5+ concern alongside the inspector.
- **Concurrent runs writing successes simultaneously** → File-per-run with atomic rename is collision-free as long as `run_id` is unique (already guaranteed).
- **Reading a partially-written success file from a crashed concurrent run** → Atomic rename means readers either see a complete file or no file; never a partial.

## Migration Plan

No migration. Existing failure-memory data on disk is read-compatible. New `successes/` directory is created on first successful run. Run-report consumers gain two optional-but-always-present fields; downstream T9 completeness checks are updated in the same change to require them.

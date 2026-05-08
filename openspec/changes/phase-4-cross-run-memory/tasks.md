## 1. Success memory store

- [x] 1.1 Add `success_memory` module mirroring the layout of `failure_memory`: resolve persistent root from `AGENT_MEMORY_DIR` (default `~/.agent/memory`), ensure `successes/` subdirectory exists.
- [x] 1.2 Define the v1 success-entry data model with required fields: `schema_version=1`, `run_id`, `timestamp` (ISO-8601 UTC), `goal`, `solution_code`, `tests`, `iterations`, `model`.
- [x] 1.3 Implement atomic write: serialize JSON, write to `<root>/successes/<run_id>.json.tmp`, fsync, rename to final path.
- [x] 1.4 Implement loader that reads and validates a single success file against the v1 schema (used by retrieval).
- [x] 1.5 Unit tests: write→read roundtrip, schema validation rejects missing/empty fields, atomic-rename leaves no `.tmp` on success path, `AGENT_MEMORY_DIR` override honored.

## 2. Memory retrieval

- [x] 2.1 Add `memory_retrieval` module exposing a single `retrieve(new_goal, root) -> RetrievalResult` entry point with `failures: list[Ref]` and `successes: list[Ref]`.
- [x] 2.2 Implement corpus loaders: scan `<root>/failures/*.jsonl` (line-by-line) and `<root>/successes/*.json`. Skip malformed entries with a warning; never crash retrieval on a bad entry.
- [x] 2.3 Implement TF-IDF cosine similarity scorer. Failure document text = `goal + " " + root_cause_summary + " " + next_hypothesis`. Success document text = `goal`. Tokenize with simple lowercase + word-boundary split.
- [x] 2.4 Apply top-K + threshold + tie-break (timestamp desc, then run_id asc). Read K from `AGENT_RETRIEVAL_K_FAILURES` (default 3), `AGENT_RETRIEVAL_K_SUCCESSES` (default 2). Threshold default `0.1`.
- [x] 2.5 Each returned `Ref` carries `path`, `run_id`, `score`, plus loaded entry payload sufficient for prompt rendering.
- [x] 2.6 Unit tests: empty corpus returns empty lists; reproducibility (same input → same output); deterministic tie-break; below-threshold candidates dropped; malformed JSONL line skipped without affecting other results.

## 3. Solve-loop integration

- [x] 3.1 Invoke `memory_retrieval.retrieve(...)` once at run start, before iteration 1's prompt is assembled. Cache result on the run-state object.
- [x] 3.2 Render the prior-run context block: heading, "Prior failures on similar goals" (each with `goal`, `error_type`, `root_cause_summary`, `next_hypothesis`), "Prior successful solutions on similar goals" (each with `goal` and a `solution_code` excerpt truncated to ≤2 KB).
- [x] 3.3 Insert the rendered block into iteration 1's prompt before the goal text. If both retrieval lists are empty, omit the block entirely (prompt is byte-identical to pre-change behavior in that case).
- [x] 3.4 Ensure later iterations reuse in-run context as before and do NOT re-invoke retrieval.
- [x] 3.5 On `outcome = "success"`, after the final iteration is accepted and before the run report is finalized, call `success_memory.write(...)` with the final iteration's code, tests, run metadata, and `iterations` count.
- [x] 3.6 Unit/integration tests: empty corpus → prompt unchanged; populated corpus → block appears with expected subsections and bounded excerpts; success run writes exactly one success file; failure / gave_up runs write zero success files.

## 4. Run report extension

- [x] 4.1 Add `retrieved_context` to the run-report schema with `failures: [...]` and `successes: [...]`, each entry carrying `path`, `run_id`, `score`. Always present, possibly empty.
- [x] 4.2 Add `success_entry` (string path on success, `null` otherwise).
- [x] 4.3 Populate both fields from the cached retrieval result and the success-memory write path.
- [x] 4.4 Update report-completeness validation (T9) to require the new fields with the documented shapes.
- [x] 4.5 Unit tests: success run report contains `success_entry` pointing to an existing file; failure/gave-up reports have `success_entry = null`; `retrieved_context` arrays correctly mirror what was injected; cited paths exist on disk.

## 5. End-to-end acceptance

- [x] 5.1 Scripted T3 scenario: run a goal that fails on the first run; on the second similar-goal run, verify the report's `retrieved_context.failures` is non-empty and references the prior run, AND iteration count is ≤ first run's iteration count.
- [x] 5.2 Scripted T7 scenario: run a goal to success; on a near-identical second run, verify `retrieved_context.successes` is non-empty and the second run completes in ≤ the first run's iteration count.
- [x] 5.3 Verify `openspec validate phase-4-cross-run-memory --strict` passes.
- [x] 5.4 Manual smoke: run on a fresh `AGENT_MEMORY_DIR` to confirm no prior corpus → empty `retrieved_context` and unchanged prompt.

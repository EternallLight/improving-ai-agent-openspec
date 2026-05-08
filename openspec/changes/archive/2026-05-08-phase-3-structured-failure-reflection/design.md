## Context

Phase 2 produced a working solve loop where each failed iteration generates an in-memory reflection that feeds the next iteration's prompt. Nothing is persisted across runs. PRD F4 requires structured failure capture on disk so a human can read what went wrong from an entry alone, and so Phase 4 can do similarity retrieval against a real corpus. This phase locks the on-disk schema and the writer contract; it does not introduce retrieval or success memory.

## Goals / Non-Goals

**Goals:**
- A stable, human-readable on-disk format for failure entries.
- Every failed iteration produces exactly one well-formed entry with all required fields.
- Entries persist beyond the run (under a configurable persistent memory root) AND are mirrored under the run workdir for traceability.
- The current run still consumes its in-memory reflections — persistence is additive, not a replacement.
- Run report surfaces failure-entry counts and paths.

**Non-Goals:**
- Cross-run retrieval or similarity search (Phase 4).
- Success memory (Phase 4).
- Inspector CLI (Phase 5).
- Schema evolution / migration tooling — this is the v1 schema.
- Indexing, embeddings, or any retrieval data structures.

## Decisions

**Format: JSONL, one file per run, plus one JSON file per entry.**
- Persistent root: `~/.agent/memory/failures/<run_id>.jsonl` (append-only, one entry per failed iteration).
- Run workdir mirror: `<workdir>/failures/iter-<N>.json` (one pretty-printed JSON file per failed iteration, easier to read by hand).
- Rationale: JSONL is the standard format for append-only ML/agent logs and trivially streamable by Phase 4. Per-iteration pretty JSON in the workdir gives a human reading the workdir an obvious place to look without parsing JSONL. Alternatives considered: single JSON document per run (rejected — append semantics are awkward); SQLite (rejected — overkill for write-only workload, harder to grep).

**Schema (v1):**
```
{
  "schema_version": 1,
  "run_id": "<uuid>",
  "iteration": <int, 1-based>,
  "timestamp": "<ISO-8601 UTC>",
  "goal": "<original goal string>",
  "error_type": "<short classifier, e.g. 'AssertionError', 'ImportError', 'ParseError', 'SandboxTimeout'>",
  "root_cause_summary": "<one-paragraph LLM-produced summary>",
  "code_or_assumptions": "<specific code lines or assumptions involved, free text or short snippet>",
  "next_hypothesis": "<what the agent intends to try next iteration>",
  "failing_test_excerpt": "<truncated pytest output, <= 4KB>"
}
```
`schema_version` is included from day one so Phase 4+ can branch cleanly without a migration tool.

**Writer module: `agent/failure_memory.py`.**
- Exposes `FailureMemoryWriter(persistent_root: Path, workdir: Path, run_id: str)` with a single `write(entry: FailureEntry) -> Path` method (returns the persistent path).
- Atomic write per entry: write to `*.tmp` then rename, so a crash mid-write never leaves a partial JSONL line.
- Persistent root is configurable via `AGENT_MEMORY_DIR` env var, defaulting to `~/.agent/memory`. Tests override it with a tmp path.

**Reflection extension.**
- `agent/reflection.py` already produces an in-memory reflection. Extend its output type so the same object carries the fields needed for a `FailureEntry` (root_cause_summary, code_or_assumptions, next_hypothesis). The LLM prompt for reflection is updated to ask for these fields explicitly in a parseable form (JSON block).
- If the LLM output cannot be parsed into the structured shape, the entry is still written with `error_type = "ParseError"` and best-effort fields, so we never silently drop a failed iteration.

**Solve loop integration.**
- `agent/solve_loop.py` calls the writer immediately after a failed iteration's reflection is produced, BEFORE starting the next iteration. This guarantees that even if the loop is killed by the circuit breaker, all prior failures are on disk.

**Run report changes.**
- Add `failure_entries`: `{ "count": <int>, "persistent_paths": [...], "workdir_paths": [...] }` to the top-level report.
- No change to `iteration_log` shape; the per-iteration `artifacts` field gains the workdir failure JSON path when applicable.

## Risks / Trade-offs

- **Schema lock-in** → Mitigation: `schema_version` field from v1; Phase 4 can read v1 and write v2 side-by-side if needed.
- **LLM produces malformed structured reflection** → Mitigation: parse defensively, fall back to `ParseError` entry rather than crash; still write something to disk.
- **Persistent dir bloat over many runs** → Mitigation: out of scope this phase; one JSONL per run keeps it manageable, and Phase 5 inspector will make it visible. No auto-pruning.
- **Concurrent runs writing to the same persistent root** → Mitigation: each run writes to its own `<run_id>.jsonl` file, so there is no shared file contention. No locking needed.
- **Workdir mirror duplicates persistent data** → Accepted trade-off: workdir is the run's self-contained record; persistent root is the cross-run corpus. Both serve different readers.

## Migration Plan

No migration — first persisted format. New runs immediately produce v1 entries. Existing Phase 2 runs leave no failure-memory artifacts; that is fine.

## Context

After phase 4, the agent has two on-disk stores under `<persistent_root>` (default `~/.agent/memory`, overridable via `AGENT_MEMORY_DIR`):

- `failures/<run_id>.jsonl` — append-only JSONL, one v1 failure entry per line.
- `successes/<run_id>.json` — one pretty-printed v1 success entry per successful run.

Today, inspecting either requires `cat`/`jq`. Phase 5 of `phases.md` adds a CLI inspector that closes PRD F9 and validates T8 ("a human can tell at a glance what the agent has learned").

## Goals / Non-Goals

**Goals:**
- A single `agent memory list` subcommand that lists entries from both stores in a compact, human-readable form.
- Filters: `--kind {failures,successes,all}`, `--limit N`, `--goal <substring>` (case-insensitive).
- Newest-first ordering by entry `timestamp`.
- Read-only: never mutates the stores.
- Honors `AGENT_MEMORY_DIR` exactly the way the writers do.

**Non-Goals:**
- No `show`/`get` subcommand for full entry contents (out of scope for T8; users can still `cat` the file).
- No deletion, editing, or export commands.
- No similarity search — that already exists in `memory-retrieval` and is not user-facing.
- No JSON output mode in this phase (text only).

## Decisions

**1. New top-level subcommand `memory`, with one verb `list`.**
Rationale: leaves room for future verbs (`show`, `prune`) without re-shaping the CLI. Alternative considered: a single flag like `agent --list-memory`, rejected because it overloads the existing `agent <goal>` entry point and conflicts with required-positional semantics.

**2. Single unified table, with a `kind` column.**
Each row: `kind  timestamp  iterations  goal  summary`. For failures, `iterations` is the iteration index of the entry and `summary` is `error_type: root_cause_summary` truncated. For successes, `iterations` is the total iteration count and `summary` is `model` plus a short "solved in N iter" tag. Rationale: one merged view answers "what has the agent learned overall" in a single glance — the T8 framing. Alternative considered: two separate tables; rejected as more verbose for the typical mixed-history case.

**3. Read both stores by directory scan, no index file.**
Rationale: stores are small (one file per run for successes, one JSONL per run for failures). A directory listing plus per-file parse is fast enough for the volumes this agent will produce, and avoids introducing an index that the writers would now have to maintain. Skip files that fail to parse with a single `stderr` warning line per bad file; never crash the listing.

**4. Truncation and column widths.**
Goal column: 60 chars. Summary column: 80 chars. Both truncated with an ellipsis. Rationale: keeps each row under a typical 200-char terminal while preserving enough context.

**5. New capability `memory-inspector` rather than extending `failure-memory`/`success-memory`.**
Rationale: the inspector is a read-only consumer; the storage specs should not grow read concerns. The `cli` spec gets a delta only for the new subcommand surface.

## Risks / Trade-offs

- [Large stores slow the scan] → Mitigated by `--limit` (applied after sort) and by the small expected volume; revisit if real usage shows it.
- [Malformed entry from a future schema version breaks parsing] → Mitigated by per-file try/except with a stderr warning; the listing continues.
- [Timestamp ordering relies on writer correctness] → Acceptable: both writers already emit ISO-8601 UTC per their specs.

## Migration Plan

None. Pure addition; no existing behavior changes.

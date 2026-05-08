## 1. Inspector module

- [x] 1.1 Add `agent/memory_inspector.py` (or equivalent) with a `list_entries(persistent_root, kind, goal_substring, limit)` function that returns an ordered list of normalized rows (dicts with `kind`, `timestamp`, `iterations`, `goal`, `summary`, `source_path`).
- [x] 1.2 Implement directory scanning: read `failures/*.jsonl` line-by-line and `successes/*.json` per file; resolve `persistent_root` from `AGENT_MEMORY_DIR` or default `~/.agent/memory`, matching the existing writers.
- [x] 1.3 Normalize each entry into a row: failure rows take `iteration` and `error_type: root_cause_summary`; success rows take `iterations` and a model + iter-count summary.
- [x] 1.4 Skip malformed entries: per-entry try/except, emit one stderr warning naming the file (and line for JSONL), continue scan.
- [x] 1.5 Apply filters in order: kind → goal substring (case-insensitive on `goal`) → newest-first sort by `timestamp` → `--limit`.

## 2. CLI wiring

- [x] 2.1 Add a `memory` subcommand group with a `list` verb to the existing CLI parser; ensure `agent <goal>` routing remains unchanged.
- [x] 2.2 Wire flags: `--kind {failures,successes,all}` (default `all`), `--limit N` (positive int), `--goal <substring>`. Reject invalid kind/limit values with non-zero exit and a single-line stderr error.
- [x] 2.3 Ensure `agent --help` mentions the `memory list` subcommand.
- [x] 2.4 Confirm `agent memory list` does not create a run directory or invoke the solve loop.

## 3. Output formatting

- [x] 3.1 Print a header row, then one row per entry, with columns: `kind  timestamp  iterations  goal  summary`.
- [x] 3.2 Truncate `goal` to 60 chars and `summary` to 80 chars with an ellipsis marker; pad columns for alignment.
- [x] 3.3 When zero entries match (empty stores or no filter hits), print a single human-readable line and exit 0.

## 4. Tests

- [x] 4.1 Unit test `list_entries` against a temp persistent root with mixed failure JSONL lines and success JSON files; assert ordering, kind filter, goal filter, limit.
- [x] 4.2 Unit test malformed-entry resilience: one bad JSONL line and one bad success file; assert valid entries still listed, single warning per bad file on stderr, exit 0.
- [x] 4.3 Unit test `AGENT_MEMORY_DIR` override.
- [x] 4.4 CLI integration test: invoke `agent memory list` end-to-end against a populated temp root; assert exit code, stdout shape, and that no files under the root were modified (snapshot mtimes/contents before/after).
- [x] 4.5 CLI test that `agent <goal>` path still runs the solve loop and does not regress.

## 5. Docs

- [x] 5.1 Update README (or equivalent) usage section with `agent memory list` examples covering each flag.

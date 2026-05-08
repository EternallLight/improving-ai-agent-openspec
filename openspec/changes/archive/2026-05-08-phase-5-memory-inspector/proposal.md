## Why

After phases 3 and 4, the agent persists structured failures and successes to disk, but the only way to inspect what it has learned is to read raw JSONL files. Phase 5 of `phases.md` calls for a human-readable inspector so a user can tell at a glance what the agent has accumulated across runs (PRD F9, acceptance test T8).

## What Changes

- Add an `agent memory list` CLI command that lists failure-memory and success-memory entries in human-readable form (goal, outcome, timestamp, short summary).
- Support filters: `--kind {failures,successes,all}` (default `all`), `--limit N`, and `--goal <substring>` for quick search.
- Default ordering: newest first by timestamp; output is a compact, columnar text format that fits standard terminals.
- No changes to memory write paths or retrieval logic — read-only consumer of the existing on-disk stores.

## Capabilities

### New Capabilities
- `memory-inspector`: read-only CLI surface over the failure-memory and success-memory stores, with filtering and human-readable formatting.

### Modified Capabilities
- `cli`: register the new `memory list` subcommand alongside the existing `agent <goal>` entry point.

## Impact

- Code: new inspector module reading from the failure-memory and success-memory store paths; CLI dispatch updated to route `memory list`.
- No new dependencies; no changes to Moonshot client, sandbox, or solve loop.
- Validates PRD acceptance test T8 and closes phase 5.

# success-memory Specification

## Purpose
TBD - created by archiving change phase-4-cross-run-memory. Update Purpose after archive.
## Requirements
### Requirement: Structured success entry schema
The system SHALL define a stable v1 schema for success entries containing the following fields, all required and non-empty: `schema_version` (integer, equal to `1`), `run_id` (string), `timestamp` (ISO-8601 UTC string), `goal` (string), `solution_code` (string, the final accepted implementation), `tests` (string, the final accepted tests), `iterations` (positive integer, count of iterations used), and `model` (string, the flagship Kimi model identifier used).

#### Scenario: Entry contains all required fields
- **WHEN** any success entry is written to disk
- **THEN** the file contents are valid JSON
- **AND** every required field is present with a non-empty value
- **AND** `schema_version` equals `1`
- **AND** `iterations` is a positive integer
- **AND** `timestamp` parses as ISO-8601 in UTC

### Requirement: Persistent storage at one file per success
The system SHALL persist a success entry exactly once per successful run to `<persistent_root>/successes/<run_id>.json` as a pretty-printed JSON file, where `<persistent_root>` defaults to `~/.agent/memory` and is overridable via the `AGENT_MEMORY_DIR` environment variable.

#### Scenario: Successful run writes one success file
- **WHEN** a run terminates with `outcome = "success"`
- **THEN** `<persistent_root>/successes/<run_id>.json` exists
- **AND** loading it yields a v1-conformant success entry whose `run_id` matches the run

#### Scenario: Non-successful runs write no success file
- **WHEN** a run terminates with `outcome = "failure"` or `outcome = "gave_up"`
- **THEN** no file is created under `<persistent_root>/successes/` for that `run_id`

#### Scenario: Honors AGENT_MEMORY_DIR override
- **WHEN** `AGENT_MEMORY_DIR` is set to a custom path and a run succeeds
- **THEN** the success JSON is written under that path's `successes/` subdirectory and not under `~/.agent/memory`

### Requirement: Atomic, crash-safe writes
The system SHALL write each success entry such that an interruption mid-write never leaves a partially written or partially renamed JSON file visible to readers.

#### Scenario: Partial writes are never visible
- **WHEN** the writer is interrupted between starting and finishing a success entry write
- **THEN** `<persistent_root>/successes/<run_id>.json` either does not exist or is a complete, parseable JSON object
- **AND** no `*.tmp` partial file is mistaken for a completed entry by readers


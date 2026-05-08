## ADDED Requirements

### Requirement: Structured failure entry schema
The system SHALL define a stable v1 schema for failure entries containing at minimum these fields, all non-empty: `schema_version` (integer, equal to `1`), `run_id` (string), `iteration` (integer, 1-based), `timestamp` (ISO-8601 UTC string), `goal` (string), `error_type` (short string classifier), `root_cause_summary` (string), `code_or_assumptions` (string), `next_hypothesis` (string), and `failing_test_excerpt` (string, truncated to at most 4 KB).

#### Scenario: Entry contains all required fields
- **WHEN** any failure entry is written to disk
- **THEN** the entry is valid JSON and contains every required field with a non-empty value
- **AND** `schema_version` equals `1`
- **AND** `iteration` is a positive integer
- **AND** `timestamp` parses as ISO-8601 in UTC

#### Scenario: Failing test excerpt is bounded
- **WHEN** raw pytest output for a failed iteration exceeds 4 KB
- **THEN** the entry's `failing_test_excerpt` is truncated to at most 4 KB with a clear truncation marker

### Requirement: Persistent and workdir-mirrored storage
The system SHALL persist failure entries to a configurable persistent memory root (defaulting to `~/.agent/memory`, overridable via the `AGENT_MEMORY_DIR` environment variable) under `failures/<run_id>.jsonl` as append-only JSONL, and SHALL also write each entry as a pretty-printed JSON file to `<workdir>/failures/iter-<N>.json` inside the run's workdir.

#### Scenario: Persistent JSONL append per failed iteration
- **WHEN** a run produces N failed iterations
- **THEN** the file `<persistent_root>/failures/<run_id>.jsonl` exists and contains exactly N lines
- **AND** each line is a parseable JSON object conforming to the v1 schema

#### Scenario: Workdir mirror per failed iteration
- **WHEN** iteration K of a run fails
- **THEN** `<workdir>/failures/iter-K.json` exists and contains the same logical entry as line K of the persistent JSONL (pretty-printed, schema-equivalent)

#### Scenario: Honors AGENT_MEMORY_DIR override
- **WHEN** `AGENT_MEMORY_DIR` is set to a custom path
- **THEN** the persistent JSONL is written under that path's `failures/` subdirectory and not under `~/.agent/memory`

### Requirement: Atomic, crash-safe writes
The system SHALL write each failure entry such that an interruption mid-write never leaves a partially written line in the persistent JSONL or a partial workdir mirror file.

#### Scenario: Partial writes leave no half-line
- **WHEN** the writer is interrupted between starting and finishing an entry write
- **THEN** the persistent JSONL contains only fully written entries (every line parses as valid JSON)
- **AND** no `*.tmp` partial file remains visible as a completed entry

### Requirement: Malformed reflection still produces an entry
The system SHALL write a failure entry for every failed iteration even when the LLM-produced structured reflection cannot be parsed into the schema. In that case `error_type` SHALL be set to `"ParseError"` and the remaining fields SHALL be populated on a best-effort basis (e.g. raw output snippet for `root_cause_summary`).

#### Scenario: Unparseable reflection
- **WHEN** an iteration fails and the LLM reflection output cannot be parsed into the structured fields
- **THEN** a failure entry is still written with `error_type = "ParseError"` and a non-empty `root_cause_summary` containing the raw reflection (truncated)

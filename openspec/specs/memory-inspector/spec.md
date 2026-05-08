# memory-inspector Specification

## Purpose
TBD - created by archiving change phase-5-memory-inspector. Update Purpose after archive.
## Requirements
### Requirement: List subcommand surfaces both memory stores
The system SHALL provide an `agent memory list` subcommand that reads the failure-memory and success-memory stores under the configured persistent root and prints one row per entry to stdout in a compact, human-readable text format.

#### Scenario: Mixed history is listed in one table
- **WHEN** the persistent root contains failure entries and success entries from prior runs
- **AND** the user runs `agent memory list`
- **THEN** stdout contains a header row and one row per entry across both stores
- **AND** each row identifies the entry kind (`failure` or `success`), its timestamp, its goal, and a short summary
- **AND** the command exits with status 0

#### Scenario: Empty stores
- **WHEN** the persistent root exists but contains no entries
- **AND** the user runs `agent memory list`
- **THEN** the command exits with status 0
- **AND** stdout contains a single human-readable line indicating that no memory entries were found

#### Scenario: Honors AGENT_MEMORY_DIR
- **WHEN** `AGENT_MEMORY_DIR` is set to a custom path containing entries
- **AND** the user runs `agent memory list`
- **THEN** entries listed are exactly those under that custom path
- **AND** no entries are read from `~/.agent/memory`

### Requirement: Newest-first ordering
The system SHALL order listed entries by their `timestamp` field in descending order (newest first) across both stores.

#### Scenario: Mixed-store ordering by timestamp
- **WHEN** a failure entry has a later `timestamp` than every success entry
- **AND** the user runs `agent memory list`
- **THEN** that failure entry appears before all success entries in the output

### Requirement: Kind filter
The system SHALL accept a `--kind` option with values `failures`, `successes`, or `all` (default `all`) and SHALL include only entries of the selected kind(s).

#### Scenario: Failures only
- **WHEN** the user runs `agent memory list --kind failures`
- **THEN** every row in the output has kind `failure`
- **AND** no success entries appear

#### Scenario: Successes only
- **WHEN** the user runs `agent memory list --kind successes`
- **THEN** every row in the output has kind `success`
- **AND** no failure entries appear

#### Scenario: Invalid kind
- **WHEN** the user runs `agent memory list --kind bogus`
- **THEN** the CLI exits with non-zero status
- **AND** stderr contains a single-line error naming the invalid value and the allowed set

### Requirement: Limit option
The system SHALL accept a `--limit N` option (positive integer) and SHALL print at most N rows after ordering and filtering have been applied.

#### Scenario: Limit caps output
- **WHEN** the stores contain more than N matching entries
- **AND** the user runs `agent memory list --limit N`
- **THEN** stdout contains exactly N entry rows (excluding the header)
- **AND** those rows are the N newest matching entries

#### Scenario: Invalid limit
- **WHEN** the user passes `--limit 0` or a non-integer value
- **THEN** the CLI exits with non-zero status and prints a single-line error to stderr

### Requirement: Goal substring filter
The system SHALL accept a `--goal <substring>` option that matches case-insensitively against each entry's `goal` field and SHALL include only matching entries.

#### Scenario: Substring match is case-insensitive
- **WHEN** an entry's goal is `"Write add(a,b) function"`
- **AND** the user runs `agent memory list --goal add`
- **THEN** that entry appears in the output

#### Scenario: No matches
- **WHEN** no entry's goal contains the given substring
- **AND** the user runs `agent memory list --goal <substring>`
- **THEN** the command exits with status 0 and stdout reports zero matches in a single human-readable line

### Requirement: Read-only operation
The system SHALL NOT create, modify, rename, or delete any file under the persistent memory root when listing entries.

#### Scenario: Listing leaves stores untouched
- **WHEN** the user runs `agent memory list` against a populated persistent root
- **THEN** the set of files under the persistent root and their contents are byte-identical before and after the command

### Requirement: Resilient to malformed entries
The system SHALL skip any individual entry that cannot be parsed against its store's v1 schema, SHALL emit one single-line warning to stderr identifying the offending file, and SHALL continue listing remaining entries.

#### Scenario: One malformed file does not abort the listing
- **WHEN** one file under `failures/` contains a malformed JSON line and the rest of the stores are valid
- **AND** the user runs `agent memory list`
- **THEN** stdout lists every valid entry from both stores
- **AND** stderr contains a single warning line naming the malformed file
- **AND** the command exits with status 0


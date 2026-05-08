## ADDED Requirements

### Requirement: Run report surfaces failure-memory entries
The run report SHALL include a top-level `failure_entries` field containing the count of structured failure entries persisted during the run and the paths to both the persistent JSONL file and each per-iteration workdir mirror file. The field SHALL be present on every run; for runs with no failed iterations the count SHALL be `0` and the path arrays SHALL be empty.

#### Scenario: Multi-iteration failing-then-succeeding run
- **WHEN** a run has K failed iterations followed by success
- **THEN** the report's `failure_entries.count` equals K
- **AND** `failure_entries.persistent_paths` lists exactly one path (the run's JSONL file) that exists on disk
- **AND** `failure_entries.workdir_paths` lists K paths, each to an existing per-iteration JSON file under the workdir

#### Scenario: Successful run with no failures
- **WHEN** a run succeeds on the first iteration
- **THEN** `failure_entries.count` equals `0`
- **AND** both path arrays are empty
- **AND** no `failures/` directory or JSONL file is created

#### Scenario: Gave-up run records all failure entries
- **WHEN** a run terminates at the circuit-breaker iteration cap with all iterations failing
- **THEN** `failure_entries.count` equals `max_iterations`
- **AND** the persistent JSONL contains exactly that many lines

## ADDED Requirements

### Requirement: Run report surfaces retrieved prior-run context
The run report SHALL include a top-level `retrieved_context` field, present on every run regardless of outcome, with two arrays: `failures` and `successes`. Each array entry SHALL contain at minimum `path` (the on-disk path of the retrieved entry), `run_id` (the source run's id), and `score` (the similarity score used for ranking). When retrieval returned no entries above threshold, both arrays SHALL be empty.

#### Scenario: Retrieved entries listed in report
- **WHEN** retrieval injected one or more failure entries and one or more success entries into iteration 1
- **THEN** `retrieved_context.failures` lists exactly those failure entries, each with `path`, `run_id`, and `score`
- **AND** `retrieved_context.successes` lists exactly those success entries, each with `path`, `run_id`, and `score`
- **AND** every cited `path` exists on disk

#### Scenario: Empty retrieval still emits the field
- **WHEN** retrieval returned no entries (empty corpus or all candidates below threshold)
- **THEN** the report contains `retrieved_context` with `failures: []` and `successes: []`

### Requirement: Run report references the persisted success entry on success
The run report SHALL include a top-level `success_entry` field. On a successful run, the field SHALL contain the on-disk path of the success-memory entry written for that run, and that path SHALL exist. On a non-successful run, the field SHALL be `null`.

#### Scenario: Success run cites the success entry path
- **WHEN** a run terminates with `outcome = "success"`
- **THEN** `success_entry` equals `<persistent_root>/successes/<run_id>.json`
- **AND** that file exists on disk and is a v1-conformant success entry

#### Scenario: Non-success run has null success_entry
- **WHEN** a run terminates with `outcome = "failure"` or `outcome = "gave_up"`
- **THEN** `success_entry` is `null`

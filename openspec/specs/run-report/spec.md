# run-report Specification

## Purpose
Defines the run report emitted by the agent at the end of every invocation, including required fields, artifact persistence, and token-cost reporting.
## Requirements
### Requirement: Run report emitted on every run
The system SHALL emit a run report at the end of every invocation, regardless of outcome (success or failure). The report SHALL be printed to stdout in human-readable form AND persisted as `run-report.json` inside the run's workdir.

#### Scenario: Successful run
- **WHEN** the agent completes a run successfully
- **THEN** a human-readable report is printed to stdout
- **AND** a `run-report.json` file exists in the workdir

#### Scenario: Failed run
- **WHEN** the agent fails (e.g. provider error)
- **THEN** a run report is still written to the workdir with `outcome` set to `"failure"` and any token usage observed before the failure

### Requirement: Report contains all required fields
The run report SHALL contain the following fields, none of which may be empty, null, or `"unknown"`: `goal`, `outcome`, `iterations`, `tokens` (with `prompt`, `completion`, `total`), `model`, `artifacts` (with at least `workdir` and `run_report` paths), `started_at`, `finished_at`, `max_iterations`, and `iteration_log` (a list with one entry per iteration attempted). Each `iteration_log` entry SHALL contain: `index` (1-based), `outcome` (`"success"`, `"failure"`, or `"sandbox_killed"`), `tokens` (prompt/completion/total for that iteration), and `artifacts` (paths to the iteration's generated code and test output, both inside the run's workdir).

`outcome` SHALL be one of `"success"`, `"failure"`, or `"gave_up"`.

#### Scenario: Field completeness on success
- **WHEN** a successful run finishes and `run-report.json` is loaded
- **THEN** every required field is present and non-empty
- **AND** `iterations` equals the number of iterations actually executed
- **AND** `tokens.total` equals the sum of `iteration_log[i].tokens.total` across iterations
- **AND** `tokens.total` equals `tokens.prompt + tokens.completion`

#### Scenario: Artifact paths resolve
- **WHEN** the report cites artifact paths (top-level or per-iteration)
- **THEN** each cited path exists on disk

#### Scenario: Gave-up run report
- **WHEN** a run terminates at the iteration cap
- **THEN** `outcome` equals `"gave_up"`, `iterations` equals `max_iterations`, and `iteration_log` contains exactly that many entries

### Requirement: Token cost reported in Moonshot tokens
The report SHALL express token cost in Moonshot tokens as returned by the provider, alongside the model name used.

#### Scenario: Tokens match provider response
- **WHEN** the Moonshot client returns a usage object with prompt/completion/total counts
- **THEN** the run report's `tokens` field equals those counts exactly
- **AND** the report's `model` field equals the model name sent to Moonshot

### Requirement: Per-iteration artifacts persisted under the workdir
For every iteration attempted, the system SHALL write the generated code, the generated tests, and the captured pytest output to files inside the run's workdir, and SHALL reference those paths from the corresponding `iteration_log` entry.

#### Scenario: Iteration artifacts on disk
- **WHEN** a multi-iteration run completes (success, failure, or gave-up)
- **THEN** the workdir contains a per-iteration subdirectory for each attempt with the generated code, tests, and pytest stdout/stderr
- **AND** the matching `iteration_log` entry's `artifacts` field points to those files

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


## MODIFIED Requirements

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

## ADDED Requirements

### Requirement: Per-iteration artifacts persisted under the workdir
For every iteration attempted, the system SHALL write the generated code, the generated tests, and the captured pytest output to files inside the run's workdir, and SHALL reference those paths from the corresponding `iteration_log` entry.

#### Scenario: Iteration artifacts on disk
- **WHEN** a multi-iteration run completes (success, failure, or gave-up)
- **THEN** the workdir contains a per-iteration subdirectory for each attempt with the generated code, tests, and pytest stdout/stderr
- **AND** the matching `iteration_log` entry's `artifacts` field points to those files

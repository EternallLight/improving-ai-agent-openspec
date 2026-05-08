## ADDED Requirements

### Requirement: Iteration-cap circuit breaker
The system SHALL terminate the solve loop when the number of completed iterations reaches a configured maximum (`max_iterations`), producing a clean `gave_up` outcome rather than continuing indefinitely.

#### Scenario: Impossible task gives up cleanly
- **WHEN** an iteration cap of N is configured and N iterations have failed
- **THEN** the loop terminates with `outcome = "gave_up"` and `iterations = N`
- **AND** the CLI exits with a non-zero status
- **AND** stderr contains a single-line message of the form "gave up after N iterations"

#### Scenario: Cap is configurable
- **WHEN** the user passes `--max-iterations 3`
- **THEN** the loop will give up after at most 3 failed iterations

#### Scenario: Default cap is sane
- **WHEN** `--max-iterations` is not provided
- **THEN** the loop uses a documented default value greater than 1

### Requirement: Gave-up runs still emit a complete run report
A run that terminates via the circuit breaker SHALL still emit a complete run report containing every required field, including the iteration log and total token usage observed.

#### Scenario: Gave-up report is well-formed
- **WHEN** a run gives up at the iteration cap
- **THEN** `run-report.json` exists with `outcome = "gave_up"`, `iterations` equal to the cap, and per-iteration entries for every iteration attempted

## ADDED Requirements

### Requirement: Iteration-cap flag
The CLI SHALL accept an optional `--max-iterations N` flag (positive integer) that sets the circuit-breaker cap for the solve loop. When omitted, a documented default SHALL be used. The chosen value SHALL be surfaced in the run report's `max_iterations` field.

#### Scenario: Explicit iteration cap
- **WHEN** the user runs `agent "<goal>" --max-iterations 3`
- **THEN** the loop runs at most 3 iterations
- **AND** the run report's `max_iterations` field equals 3

#### Scenario: Default iteration cap
- **WHEN** the user runs `agent "<goal>"` without `--max-iterations`
- **THEN** the loop uses the default cap and the run report records that value in `max_iterations`

#### Scenario: Invalid iteration cap
- **WHEN** the user passes `--max-iterations 0` or a non-integer value
- **THEN** the CLI exits with non-zero status and prints a single-line error to stderr

### Requirement: Non-zero exit on gave-up outcome
The CLI SHALL exit with a non-zero status when the run ends with `outcome = "gave_up"` and SHALL print a single-line message to stderr identifying the iteration cap that was hit.

#### Scenario: Gave up at cap
- **WHEN** the loop terminates via the circuit breaker
- **THEN** the CLI exits non-zero and stderr contains a single-line message of the form "gave up after N iterations"
- **AND** the run report has been written to the workdir before exit

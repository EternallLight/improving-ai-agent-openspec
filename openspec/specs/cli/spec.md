# cli Specification

## Purpose
Defines the command-line interface for the agent: how users supply a goal, where artifacts are written, and how the CLI is invoked and reports failures.
## Requirements
### Requirement: Goal intake from the command line
The system SHALL provide an `agent` command that accepts a single positional `goal` argument (a natural-language coding task) and an optional `--workdir DIR` argument selecting where artifacts are written.

#### Scenario: Goal provided with default workdir
- **WHEN** the user runs `agent "write add(a,b)"` with no `--workdir`
- **THEN** the CLI accepts the goal and creates a timestamped run directory under `./.agent-runs/`
- **AND** the run proceeds end-to-end without prompting for further input

#### Scenario: Explicit workdir
- **WHEN** the user runs `agent "<goal>" --workdir /tmp/run1`
- **THEN** the CLI uses `/tmp/run1` (creating it if absent) as the workdir for all artifacts

#### Scenario: Missing goal
- **WHEN** the user runs `agent` with no positional argument
- **THEN** the CLI exits with a non-zero status and prints usage to stderr

### Requirement: Console-script entry point
The system SHALL expose the CLI as both `agent` (console script) and `python -m agent`, both of which invoke the same entry point.

#### Scenario: Console script
- **WHEN** the package is installed and the user runs `agent --help`
- **THEN** usage is printed and exit code is 0

#### Scenario: Module invocation
- **WHEN** the user runs `python -m agent --help`
- **THEN** the same usage is printed and exit code is 0

### Requirement: Non-zero exit on failure
The CLI SHALL exit with a non-zero status code when the run cannot complete (e.g. missing API key, network failure, provider error), and SHALL print a single-line error to stderr identifying the cause.

#### Scenario: Missing MOONSHOT_API_KEY
- **WHEN** `MOONSHOT_API_KEY` is unset and the user runs `agent "<goal>"`
- **THEN** the CLI exits with a non-zero status
- **AND** stderr contains a message naming the missing environment variable

#### Scenario: Provider error
- **WHEN** the Moonshot API returns a non-success response
- **THEN** the CLI exits with a non-zero status and writes a failure run report to the workdir

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


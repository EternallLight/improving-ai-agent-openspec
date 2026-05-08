# solve-loop Specification

## Purpose
The solve-loop capability defines the iterative generate → test → reflect cycle that drives the agent toward a working solution. Each iteration prompts the LLM for code and tests, runs them in the sandbox, and on failure produces a structured reflection that informs the next iteration. The loop terminates on test success or when the circuit-breaker iteration cap is reached.
## Requirements
### Requirement: Generate → test → reflect iteration
The system SHALL execute a solve loop in which each iteration (a) prompts the LLM to produce both implementation code and pytest tests for the goal, (b) runs the tests inside the sandbox, and (c) on test failure produces a structured in-memory reflection that is included in the prompt for the next iteration.

#### Scenario: Trivial task succeeds in one iteration
- **WHEN** the agent is given a trivial single-file Python goal (e.g. "implement add(a, b)")
- **THEN** the loop terminates after exactly 1 iteration with `outcome = "success"`
- **AND** the run report records 1 iteration

#### Scenario: Non-trivial task succeeds after multiple iterations
- **WHEN** the first iteration's tests fail and the next iteration uses the reflection to correct the code
- **THEN** the loop continues until tests pass and terminates with `outcome = "success"`
- **AND** the run report records `iterations > 1`
- **AND** each failed iteration's reflection was passed into the next iteration's prompt

#### Scenario: Reflection is structured
- **WHEN** an iteration's tests fail
- **THEN** the in-memory reflection passed forward contains at minimum: iteration index, the failing test output (truncated), and an LLM-produced short root-cause summary

### Requirement: Loop terminates on success or circuit-breaker
The solve loop SHALL terminate as soon as a sandboxed test run reports all tests passing, or when the circuit-breaker iteration cap is reached, whichever comes first. The loop SHALL NOT terminate on transient errors that are recoverable in the next iteration (e.g. malformed model output).

#### Scenario: Success terminates immediately
- **WHEN** an iteration's pytest exit code indicates all tests passed
- **THEN** the loop returns `outcome = "success"` without running another iteration

#### Scenario: Malformed model output does not abort the run
- **WHEN** an iteration's model output cannot be parsed into code + tests
- **THEN** that iteration is recorded as a failed iteration with a reflection noting the parse failure
- **AND** the loop continues to the next iteration (until the cap)

### Requirement: In-memory only this phase
The solve loop SHALL keep all reflection state in process memory only. No reflection or per-iteration state SHALL be written to a persistent store outside the run's workdir during this phase.

#### Scenario: No cross-run state written
- **WHEN** a multi-iteration run completes
- **THEN** no files are written outside the run's workdir for the purpose of feeding future runs

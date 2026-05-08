# solve-loop Specification

## Purpose
The solve-loop capability defines the iterative generate → test → reflect cycle that drives the agent toward a working solution. Each iteration prompts the LLM for code and tests, runs them in the sandbox, and on failure produces a structured reflection that informs the next iteration. The loop terminates on test success or when the circuit-breaker iteration cap is reached.
## Requirements
### Requirement: Generate → test → reflect iteration
The system SHALL execute a solve loop in which each iteration (a) prompts the LLM to produce both implementation code and pytest tests for the goal, (b) runs the tests inside the sandbox, and (c) on test failure produces a structured reflection that is included in the prompt for the next iteration AND is the source for the persisted failure-memory entry.

#### Scenario: Trivial task succeeds in one iteration
- **WHEN** the agent is given a trivial single-file Python goal (e.g. "implement add(a, b)")
- **THEN** the loop terminates after exactly 1 iteration with `outcome = "success"`
- **AND** the run report records 1 iteration
- **AND** no failure entries are written

#### Scenario: Non-trivial task succeeds after multiple iterations
- **WHEN** the first iteration's tests fail and the next iteration uses the reflection to correct the code
- **THEN** the loop continues until tests pass and terminates with `outcome = "success"`
- **AND** the run report records `iterations > 1`
- **AND** each failed iteration's reflection was passed into the next iteration's prompt
- **AND** one failure entry per failed iteration was persisted

#### Scenario: Reflection is structured
- **WHEN** an iteration's tests fail
- **THEN** the reflection passed forward AND used to build the failure entry contains at minimum: iteration index, the failing test output (truncated), an LLM-produced short root-cause summary, the code or assumptions involved, and the next-iteration hypothesis

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
The solve loop SHALL keep its iteration-to-iteration reflection state in process memory for prompt-feeding purposes, AND SHALL additionally persist a structured failure entry to disk for every failed iteration through the `failure-memory` capability before the next iteration begins. No other per-iteration state SHALL be written to a persistent store outside the run's workdir during this phase.

#### Scenario: Failed iteration persists a structured entry
- **WHEN** an iteration fails (test failure, sandbox kill, or parse error)
- **THEN** a failure entry conforming to the failure-memory v1 schema is written to both the persistent root and the run workdir before the next iteration starts

#### Scenario: Persistence survives circuit-breaker termination
- **WHEN** the loop terminates via the circuit breaker after K failed iterations
- **THEN** the persistent JSONL for the run contains exactly K entries

#### Scenario: No other cross-run state written
- **WHEN** a multi-iteration run completes
- **THEN** no files other than failure-memory entries are written outside the run's workdir for the purpose of feeding future runs

### Requirement: Iteration 1 prompt includes retrieved prior-run context
The solve loop SHALL invoke the `memory-retrieval` capability exactly once at run start and SHALL include the returned failures and successes in iteration 1's prompt as a clearly-labeled prior-run context block placed before the goal. The block SHALL contain two subsections — "Prior failures on similar goals" rendering each failure's `goal`, `error_type`, `root_cause_summary`, and `next_hypothesis`; and "Prior successful solutions on similar goals" rendering each success's `goal` plus a code excerpt from `solution_code` truncated to at most 2 KB per entry. If retrieval returns no entries for either category after threshold filtering, the prior-run context block SHALL be omitted entirely from the prompt.

#### Scenario: Empty corpora leave the prompt unchanged
- **WHEN** retrieval returns zero failures and zero successes
- **THEN** iteration 1's prompt contains no prior-run context block
- **AND** the prompt is otherwise identical to the prompt the loop would have produced before this change

#### Scenario: Retrieved failures appear in iteration 1 prompt
- **WHEN** retrieval returns one or more failure entries above threshold for the new goal
- **THEN** iteration 1's prompt contains a "Prior failures on similar goals" subsection listing each returned failure's `goal`, `error_type`, `root_cause_summary`, and `next_hypothesis`
- **AND** the subsection appears before the new goal text

#### Scenario: Retrieved successes appear in iteration 1 prompt with bounded excerpts
- **WHEN** retrieval returns one or more success entries above threshold for the new goal
- **THEN** iteration 1's prompt contains a "Prior successful solutions on similar goals" subsection listing each returned success's `goal` and a `solution_code` excerpt
- **AND** each rendered code excerpt is at most 2 KB

#### Scenario: Iterations after the first do not re-retrieve
- **WHEN** iteration 2 or later runs in the same run
- **THEN** retrieval is not invoked again
- **AND** the prior-run context injected at iteration 1 may continue to be carried forward by the loop's existing in-run context but no new retrieval reads occur

### Requirement: Success persistence on successful termination
On every run that terminates with `outcome = "success"`, the solve loop SHALL persist exactly one success entry through the `success-memory` capability before the run report is finalized. The entry's `iterations` field SHALL equal the number of iterations actually executed in the run, and its `goal`, `solution_code`, and `tests` SHALL reflect the inputs/outputs of the final, passing iteration.

#### Scenario: Success persists one entry per successful run
- **WHEN** a run terminates with `outcome = "success"` after K iterations
- **THEN** a single success entry exists at `<persistent_root>/successes/<run_id>.json` whose `iterations` equals K and whose `solution_code` and `tests` match the final iteration's accepted code and tests

#### Scenario: Non-successful runs persist no success entry
- **WHEN** a run terminates with `outcome = "failure"` or `outcome = "gave_up"`
- **THEN** no success entry is written for that `run_id`


## ADDED Requirements

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

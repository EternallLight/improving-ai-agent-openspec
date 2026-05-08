# memory-retrieval Specification

## Purpose
TBD - created by archiving change phase-4-cross-run-memory. Update Purpose after archive.
## Requirements
### Requirement: Retrieval over both stores at run start
At the start of every solve-loop run, before iteration 1 prompts the LLM, the system SHALL execute one retrieval pass that returns up to `top_k_failures` failure entries and up to `top_k_successes` success entries scored by similarity to the new goal. Defaults: `top_k_failures = 3`, `top_k_successes = 2`. The defaults SHALL be overridable via environment variables `AGENT_RETRIEVAL_K_FAILURES` and `AGENT_RETRIEVAL_K_SUCCESSES`.

#### Scenario: Retrieval runs once per run
- **WHEN** any run starts
- **THEN** retrieval is invoked exactly once before iteration 1
- **AND** retrieval is not invoked again during the run

#### Scenario: Empty corpora produce empty results
- **WHEN** no failure entries and no success entries exist on disk under the persistent root
- **THEN** retrieval returns empty lists for both failures and successes
- **AND** the run proceeds normally with no prior-run context injection

### Requirement: Deterministic similarity scoring
The system SHALL score candidates against the new goal using a deterministic similarity function (lexical TF-IDF cosine over the candidate's `goal` text, augmented for failure entries by `root_cause_summary` and `next_hypothesis`). Scores SHALL be reproducible: re-running retrieval on the same corpus and the same new goal produces identical ranked results.

#### Scenario: Reproducibility
- **WHEN** retrieval is run twice with the same persistent corpus and the same new goal
- **THEN** both runs return the same ordered list of entry references with the same scores

#### Scenario: Tie-break is deterministic
- **WHEN** two candidate entries share an identical similarity score
- **THEN** the entry with the more recent `timestamp` ranks first
- **AND** if timestamps are also equal, the entry with the lexicographically smaller `run_id` ranks first

### Requirement: Minimum-score threshold filters noise
The system SHALL drop any candidate whose similarity score is below a minimum threshold (default `0.1`) before returning results, even if that produces fewer than `top_k_*` entries.

#### Scenario: Below-threshold candidates are dropped
- **WHEN** the highest-scoring failure candidate scores below `0.1` for a given new goal
- **THEN** retrieval returns no failure entries for that run

#### Scenario: Mixed threshold results
- **WHEN** two of three top failure candidates score above threshold and one below
- **THEN** retrieval returns exactly two failure entries, ranked by score

### Requirement: Retrieval result shape
Retrieval SHALL return, for each entry it includes, at minimum: the entry's source path on disk, the entry's `run_id`, the similarity `score`, and the entry payload sufficient for prompt rendering (`goal` plus failure-specific or success-specific fields per the respective schemas).

#### Scenario: Result references are loadable
- **WHEN** retrieval returns an entry reference
- **THEN** the cited path exists on disk
- **AND** loading the file yields a schema-conformant entry whose `run_id` equals the reference's `run_id`


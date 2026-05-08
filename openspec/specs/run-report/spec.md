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
The run report SHALL contain the following fields, none of which may be empty, null, or `"unknown"`: `goal`, `outcome`, `iterations`, `tokens` (with `prompt`, `completion`, `total`), `model`, `artifacts` (with at least `workdir` and `run_report` paths), `started_at`, and `finished_at`.

#### Scenario: Field completeness on success
- **WHEN** a successful run finishes and `run-report.json` is loaded
- **THEN** every required field is present and non-empty
- **AND** `iterations` equals `1` (Phase 1 makes exactly one LLM call)
- **AND** `tokens.total` equals `tokens.prompt + tokens.completion`

#### Scenario: Artifact paths resolve
- **WHEN** the report cites artifact paths
- **THEN** each cited path exists on disk

### Requirement: Token cost reported in Moonshot tokens
The report SHALL express token cost in Moonshot tokens as returned by the provider, alongside the model name used.

#### Scenario: Tokens match provider response
- **WHEN** the Moonshot client returns a usage object with prompt/completion/total counts
- **THEN** the run report's `tokens` field equals those counts exactly
- **AND** the report's `model` field equals the model name sent to Moonshot

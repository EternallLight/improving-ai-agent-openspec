## ADDED Requirements

### Requirement: Memory inspector subcommand
The CLI SHALL register a `memory` subcommand group with one verb `list` (`agent memory list`) that dispatches to the `memory-inspector` capability. The subcommand SHALL coexist with the existing positional-goal entry point such that `agent <goal>` continues to behave as before and `agent memory list` is unambiguously routed to the inspector.

#### Scenario: Memory list routes to inspector
- **WHEN** the user runs `agent memory list`
- **THEN** the inspector runs and the solve loop is not invoked
- **AND** no run directory is created under `./.agent-runs/`

#### Scenario: Goal entry point still works
- **WHEN** the user runs `agent "<goal>"` with a non-`memory` first argument
- **THEN** the existing goal-intake behavior runs unchanged

#### Scenario: Help lists the subcommand
- **WHEN** the user runs `agent --help`
- **THEN** stdout includes a reference to the `memory list` subcommand

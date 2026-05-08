## ADDED Requirements

### Requirement: Process-level sandbox with scratch directory
The system SHALL execute model-generated code only inside a per-iteration sandbox that uses a fresh writable scratch directory under the OS temp dir as its working directory. The sandbox SHALL be implemented as a child process with POSIX resource limits, not by exec'ing into the parent.

#### Scenario: Fresh scratch dir per iteration
- **WHEN** an iteration begins
- **THEN** a new scratch directory is created under `tempfile.gettempdir()` and used as the child process `cwd`
- **AND** prior iterations' scratch directories have already been removed

#### Scenario: Filesystem escape blocked
- **WHEN** the model emits a target path that, after `Path.resolve()`, lies outside the scratch directory
- **THEN** the file is not written, the iteration is recorded as failed, and the loop continues with a reflection naming the rejected path

### Requirement: CPU and wall-clock limits
The sandbox SHALL enforce both a CPU-time limit (via `RLIMIT_CPU`) and a wall-clock timeout on every test execution. When either limit is exceeded the sandbox SHALL kill the entire child process group and report the iteration as a sandbox-terminated failure.

#### Scenario: Runaway code is killed within the limit
- **WHEN** an iteration's generated code contains an infinite loop
- **THEN** the sandbox kills the child process group within the configured wall-clock limit
- **AND** the iteration is recorded as a failed iteration with reflection noting "killed by sandbox"
- **AND** no orphaned child processes remain after the run completes

### Requirement: Guaranteed cleanup of processes and scratch directories
The sandbox SHALL guarantee that, after each iteration and at the end of the run, no child processes spawned by the sandbox remain alive and no scratch directories created by the sandbox remain on disk, regardless of iteration outcome (success, failure, timeout, or unexpected exception).

#### Scenario: Cleanup on success
- **WHEN** an iteration completes successfully
- **THEN** its scratch dir is deleted before the next iteration starts (or before the run returns)

#### Scenario: Cleanup on timeout
- **WHEN** an iteration is killed by the wall-clock limit
- **THEN** the child process group is reaped and the scratch dir is deleted before the loop continues

#### Scenario: Cleanup on exception
- **WHEN** an unexpected exception is raised inside the sandbox runner
- **THEN** the scratch dir is still removed and any spawned processes are terminated before the exception propagates

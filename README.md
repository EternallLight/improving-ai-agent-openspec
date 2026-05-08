# agent

Self-improving coding agent. Phase 2 ships a solve loop: each iteration generates code + pytest tests via Moonshot, runs them in a process-level sandbox, and reflects on failure.

## Usage

```bash
agent "<goal>" [--workdir <path>] [--model <name>] [--max-iterations N]
```

### Flags

- `--workdir` — directory for run artifacts. Defaults to `./.agent-runs/<utc-timestamp>/`.
- `--model` — override the Moonshot model (defaults to `MOONSHOT_MODEL` env var, then `kimi-k2-0905-preview`).
- `--max-iterations N` — circuit-breaker cap on solve-loop iterations (default: `5`, must be `>= 1`).

### Outcomes

The run report's `outcome` field is one of:

- `success` — pytest passed in some iteration. Exit code `0`.
- `gave_up` — circuit breaker hit `max_iterations` without success. Exit code non-zero; stderr contains `gave up after N iterations`.
- `failure` — unexpected error before/around the loop (e.g. missing API key). Exit code non-zero.

### Run report

Written to `<workdir>/run-report.json` with per-iteration entries under `iteration_log`. Each entry references its generated `code.py`, `test_code.py`, and captured `pytest.stdout`/`pytest.stderr` under `<workdir>/iter-<N>/`.

## Setup

```bash
python -m venv .venv && . .venv/bin/activate
pip install -e ".[dev]"
export MOONSHOT_API_KEY=...
```

Run the tests:

```bash
pytest
```

## Limits

- Sandbox is process-level (POSIX `RLIMIT_CPU` + `os.setsid` + wall-clock kill). macOS/Linux only.
- Network I/O is not blocked at the kernel level this phase.
- Reflections are in-memory only; persistence and cross-run memory land in later phases.

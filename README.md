# agent

Self-improving coding agent. Each iteration generates code + pytest tests via Moonshot, runs them in a process-level sandbox, and reflects on failure. Failures and successes persist across runs and are retrieved by similarity to seed future attempts.

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

### Inspecting memory

After runs persist failures and successes under `~/.agent/memory` (override with `AGENT_MEMORY_DIR`), list them with:

```bash
agent memory list                              # newest-first across both stores
agent memory list --kind failures              # failures only
agent memory list --kind successes --limit 5   # 5 newest successes
agent memory list --goal add                   # case-insensitive goal substring filter
```

The command is read-only and never invokes the solve loop. Output is a compact `kind / timestamp / iters / goal / summary` table.

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
- Network I/O is not blocked at the kernel level.
- Cross-run retrieval uses TF-IDF cosine over goal text — no embeddings.

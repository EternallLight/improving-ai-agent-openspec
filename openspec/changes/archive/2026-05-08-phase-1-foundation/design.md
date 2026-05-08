## Context

This is Phase 1 of the self-improving coding agent (see `prd.md` and `phases.md`). The PRD pins the LLM provider to Moonshot (Kimi) only, accessed via Moonshot's OpenAI-compatible endpoint at `https://api.moonshot.ai/v1` using `MOONSHOT_API_KEY`. No solve loop, sandbox, or memory exists yet — those land in Phases 2–5. Phase 1 only needs to prove the foundation runs end-to-end: CLI → single LLM call → fully populated run report.

The interfaces established here (`LLMClient`, run-report shape, package layout) become load-bearing for every later phase, so they should be small but stable.

## Goals / Non-Goals

**Goals:**
- A `agent <goal> [--workdir DIR]` CLI that runs end-to-end against the live Moonshot API.
- A minimal `LLMClient` interface with one Moonshot implementation, returning both content and token-usage data.
- A run-report module that emits a complete report (no `"unknown"` fields) covering goal, outcome, iterations (= 1), token cost, and artifact paths.
- Project scaffolding (Python package, `pyproject.toml`, console-script entry point) ready for later phases to extend.

**Non-Goals:**
- Iteration loop, reflection, or retries (Phase 2).
- Sandboxing or pytest execution (Phase 2).
- Any persistence beyond writing the artifacts produced this run (Phases 3–4).
- Memory inspector CLI (Phase 5).
- Streaming output, multi-provider support, or any non-Moonshot client.

## Decisions

### Language & runtime: Python 3.11+
The PRD constrains generated code to Python and the agent itself is small; keeping host and target in one language simplifies later phases (sandboxed pytest, AST work for memory). Alternatives considered: Node/TypeScript (rejected — would force a second runtime once Phase 2 runs pytest).

### LLM transport: official `openai` Python SDK pointed at Moonshot's base URL
Moonshot exposes an OpenAI-compatible API. Using `openai` with `base_url="https://api.moonshot.ai/v1"` and `api_key=os.environ["MOONSHOT_API_KEY"]` gives us battle-tested HTTP, retries, and a `usage` object for token accounting. Alternatives: raw `httpx` (rejected — reimplements retry/usage parsing); a Moonshot-specific SDK (rejected — no benefit, ties us to a single vendor's client surface even though the *provider* is already pinned).

### `LLMClient` interface shape
A single method, `complete(messages: list[Message], *, model: str | None = None) -> LLMResponse`, where `LLMResponse` carries `content: str` and `usage: TokenUsage(prompt, completion, total)`. Kept deliberately narrow so Phase 2's reflect/generate calls don't have to redesign it. Alternatives: a richer interface with streaming/tool-calls (rejected — YAGNI for Phase 1, easier to extend than retract).

### Model selection
Default to Moonshot's flagship coding-tier model (configurable via `--model` and `MOONSHOT_MODEL` env var, falling back to a hardcoded default like `kimi-k2-0905-preview`). Phase 1 only makes one call so the "smaller model for similarity" split from the PRD is deferred to Phase 4.

### CLI framework: `argparse` (stdlib)
Two positional/optional args — `goal` and `--workdir` — don't justify a dependency. Alternatives: `click`/`typer` (rejected for Phase 1; revisit if Phase 5's inspector grows subcommands).

### Workdir resolution
If `--workdir` is omitted, create a timestamped subdirectory under `./.agent-runs/<UTC-timestamp>/`. The directory is created eagerly so the run report can always cite a real path. Phase 2 will reuse this as the sandbox scratch root.

### Run report shape
Emit both human-readable stdout *and* a `run-report.json` written into the workdir. JSON shape:
```
{
  "goal": str,
  "outcome": "success" | "failure" | "gave_up",
  "iterations": int,
  "tokens": {"prompt": int, "completion": int, "total": int},
  "model": str,
  "artifacts": {"workdir": str, "run_report": str, "llm_response": str},
  "started_at": ISO8601,
  "finished_at": ISO8601
}
```
Phase 1 always reports `outcome: "success"` if the LLM call returned and `iterations: 1`. The on-disk JSON keeps the report machine-checkable for the T9 acceptance test.

### Artifact: raw LLM response
Phase 1 has no generated code yet, so the only "produced artifact" besides the report is the raw assistant message. Persist it as `<workdir>/llm-response.txt` so the report has a real artifact path to cite (no `"unknown"` fields).

### Error handling
Missing `MOONSHOT_API_KEY`, network/HTTP failures, and non-200 responses surface as a non-zero exit with a single-line error to stderr. Still write a partial run report to disk with `outcome: "failure"` and zero token usage so downstream tooling has a consistent shape.

### Package layout
```
agent/
  __init__.py
  __main__.py        # python -m agent
  cli.py             # argparse + entry point
  llm/
    __init__.py
    client.py        # LLMClient protocol, Message, LLMResponse, TokenUsage
    moonshot.py      # MoonshotClient
  report.py          # RunReport dataclass + serialize/print
pyproject.toml       # console-script: agent = "agent.cli:main"
```

## Risks / Trade-offs

- **Live-API dependency for the smoke test** → Mitigation: gate the live call behind a single integration test marked `@pytest.mark.live`; unit tests use a fake `LLMClient`.
- **Interface lock-in across phases** → Mitigation: keep `LLMClient` to one method; expand it in a follow-up change rather than over-engineering now.
- **Moonshot model name drift** → Mitigation: model is overridable via flag and env var; default lives in one constant.
- **Workdir collisions on rapid invocations** → Mitigation: timestamp includes microseconds; fall back to `mkdtemp` on collision.
- **Token-cost reporting in tokens, not dollars** → Accepted: the PRD says "Moonshot tokens / pricing"; we report raw tokens + model and leave $ conversion for a later phase if needed.

## Migration Plan

Greenfield — no migration. Rollback = delete the `agent/` package and `pyproject.toml`.

## Open Questions

- Exact default model string (`kimi-k2-0905-preview` vs. current flagship at build time). Resolve by checking Moonshot's published model list at implementation time.
- Whether the run report should also surface the user's prompt verbatim. Leaning yes (debuggability), but not blocking.

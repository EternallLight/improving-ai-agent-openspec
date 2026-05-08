## Why

Phase 1 of the self-improving coding agent needs a runnable foundation before the solve loop, sandbox, or memory can be layered on. Without a CLI entry point, a working Moonshot client, and a complete run-report skeleton, every later phase has nothing concrete to extend and no way to verify its provider/cost contract.

## What Changes

- Add an `agent <goal> [--workdir DIR]` CLI that accepts a natural-language goal and an optional working directory.
- Add a clean `LLMClient` interface with a single Moonshot (Kimi) implementation, authenticated via `MOONSHOT_API_KEY` against `https://api.moonshot.ai/v1` (OpenAI-compatible).
- Make a single Moonshot completion call per run using the flagship Kimi model for generate/reflect-class calls.
- Emit a complete run report containing: goal, outcome, iterations used (always 1 in this phase), total Moonshot token cost, and paths to produced artifacts. No field may be empty or `"unknown"`.
- Establish project scaffolding (package layout, dependency manifest, entry point) that later phases will extend.

Out of scope for this phase: solve loop, sandboxed execution, failure/success memory, memory inspector.

## Capabilities

### New Capabilities
- `cli`: Command-line entry point for invoking the agent with a goal and optional workdir.
- `llm-client`: Provider-abstracted LLM client interface with the sole Moonshot implementation, including token-usage accounting.
- `run-report`: End-of-run structured report covering goal, outcome, iteration count, token cost, and artifact paths.

### Modified Capabilities
<!-- None — no prior specs exist. -->

## Impact

- New Python package (e.g. `agent/`) with CLI entry point, `LLMClient` interface, Moonshot client, and run-report module.
- New dependency manifest (e.g. `pyproject.toml`) pinning an HTTP/OpenAI-compatible client suitable for Moonshot.
- Requires `MOONSHOT_API_KEY` in the environment at runtime.
- Establishes interfaces (`LLMClient`, run-report shape) that Phases 2–5 will extend; changing them later will be a breaking change to downstream phases.
- Validates PRD acceptance test T9 in trivial form (single-iteration run report completeness).

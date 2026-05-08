# Phases — Self-Improving Coding Agent

Split of `prd.md` into five sequential phases, each sized for one OpenSpec
propose → apply → archive cycle. Each phase ends on a runnable agent that
passes a named subset of the PRD acceptance tests.

Provider constraint applies to every phase: Moonshot (Kimi) only, via
`MOONSHOT_API_KEY` against `https://api.moonshot.ai/v1` (OpenAI-compatible).
Flagship Kimi model for generate/reflect; smaller Kimi model permitted for
similarity / formatting calls.

---

## Phase 1 — Foundation: CLI, Moonshot client, run report skeleton

**PRD coverage:** F1 (goal intake), F8 (run report), provider constraint.

**Deliverable:** `agent <goal> [--workdir DIR]` CLI that calls Moonshot once
and prints a full run report containing: goal, outcome, iterations used (will
be 1 here), total Moonshot token cost, paths to produced artifacts. Clean
`LLMClient` interface with a single Moonshot implementation.

**Out of scope this phase:** solve loop, sandbox, memory.

**Validates:** T9 (run-report completeness, in trivial form).

**Done when:** running the CLI on any goal produces a populated report with
no "unknown" fields and a real Moonshot token count.

---

## Phase 2 — Solve loop + sandbox + circuit breaker

**PRD coverage:** F2 (generate → test → reflect loop, in-run only — no
cross-run memory yet), F3 (process-level sandbox with CPU/time limit and
writable scratch dir), F7 (circuit breaker on iteration limit).

**Deliverable:** end-to-end agent that solves single-file Python tasks. Each
iteration generates code + tests, runs pytest inside the sandbox, and on
failure produces an in-memory reflection that feeds the next iteration. Loop
terminates on success or at the configured iteration cap with a clean
"gave up after N iterations" status. No orphaned processes or scratch dirs.

**Out of scope this phase:** structured persisted failure entries,
cross-run memory, memory inspector.

**Validates:** T1, T2, T4, T5, T9 (full).

**Done when:** the trivial task passes in 1 iteration, the non-trivial task
passes in >1 iteration, the impossible task gives up cleanly, and the
sandbox blocks filesystem escape and kills runaway code within the limit.

---

## Phase 3 — Structured failure reflection (write-only persistence)

**PRD coverage:** F4 (structured failure capture).

**Deliverable:** every failed iteration writes a structured entry to disk
containing at minimum: goal, error type, short root-cause summary, the
specific code lines or assumptions involved, and the agent's hypothesis for
what to try next. Format is stable and human-readable (e.g. JSONL or one
file per entry). Entries still feed the *current run's* next iteration; no
cross-run retrieval yet.

**Out of scope this phase:** similarity-based retrieval, success memory,
inspector CLI.

**Validates:** T6 (failure capture quality — structured, not raw stack
traces; a human can understand what went wrong from the entry alone).

**Done when:** after a multi-iteration failing-then-succeeding run, the
on-disk entries are well-formed and each contains all required fields.

---

## Phase 4 — Cross-run memory: failure retrieval + success memory

**PRD coverage:** F5 (persistent failure memory with similarity retrieval
into starting context), F6 (persistent success memory of goal + working
solution).

**Deliverable:** at the start of each run, retrieve the most relevant past
failures and successes by similarity to the new goal and inject them into
the agent's starting context. On success, store goal + working solution.
This is the self-improvement proof point.

**Out of scope this phase:** inspector CLI (next phase).

**Validates:** T3 (self-improvement across runs — second similar task uses
fewer iterations and its starting context references the prior failure),
T7 (success pattern reuse — near-identical task is faster on the second
run and references the stored solution).

**Done when:** T3 and T7 both pass with verifiable evidence in the run
report (retrieved entries listed) and reduced iteration count.

---

## Phase 5 — Memory inspector CLI

**PRD coverage:** F9 (inspectable memory).

**Deliverable:** a CLI command (e.g. `agent memory list`, with sensible
filters) that lists failure-memory and success-memory entries in
human-readable form, including goals, outcomes, and timestamps.

**Validates:** T8 (memory inspector — user can tell at a glance what the
agent has learned).

**Done when:** after several mixed runs, the inspector cleanly lists both
stores and a human can read the output without consulting raw files.

---

## Sequencing notes

- Sandbox lands with the loop in P2, not earlier — nothing to sandbox in P1,
  and bolting it on later would force a refactor of the iteration runner.
- Memory is split into *write* (P3) and *retrieve-across-runs* (P4) so the
  structured-capture contract is locked before similarity logic layers on.
- All nine PRD acceptance tests (T1–T9) are covered by the end of P5; the
  run is "complete" per the PRD when all pass against the final build.

## 1. Project scaffolding

- [x] 1.1 Create `pyproject.toml` (Python ≥3.11) with `openai` and `pytest` dependencies and a console-script entry point `agent = "agent.cli:main"`
- [x] 1.2 Create the `agent/` package layout (`__init__.py`, `__main__.py`, `cli.py`, `llm/__init__.py`, `llm/client.py`, `llm/moonshot.py`, `report.py`)
- [x] 1.3 Add a `.gitignore` entry for `.agent-runs/` and verify `python -m agent --help` runs from a fresh install

## 2. LLM client interface

- [x] 2.1 In `agent/llm/client.py`, define `Message` (role/content), `TokenUsage(prompt, completion, total)`, `LLMResponse(content, usage)`, and the `LLMClient` Protocol with `complete(messages, *, model=None) -> LLMResponse`
- [x] 2.2 Add a `FakeLLMClient` in tests that returns canned `LLMResponse` values for unit tests
- [x] 2.3 Unit-test the protocol shape: `FakeLLMClient` is statically and structurally a valid `LLMClient`

## 3. Moonshot client

- [x] 3.1 In `agent/llm/moonshot.py`, implement `MoonshotClient` using the `openai` SDK with `base_url="https://api.moonshot.ai/v1"` and `api_key=os.environ["MOONSHOT_API_KEY"]`
- [x] 3.2 Read default model from `MOONSHOT_MODEL` env var, falling back to a hardcoded flagship Kimi model constant
- [x] 3.3 Parse `usage` from the Moonshot response into `TokenUsage` and return an `LLMResponse`
- [x] 3.4 Raise a clear `RuntimeError` (naming `MOONSHOT_API_KEY`) when the env var is missing
- [x] 3.5 Add a live integration test marked `@pytest.mark.live` that issues one real Moonshot call and asserts non-empty content + non-zero token totals

## 4. Run report

- [x] 4.1 In `agent/report.py`, define a `RunReport` dataclass with fields `goal`, `outcome`, `iterations`, `tokens`, `model`, `artifacts`, `started_at`, `finished_at`
- [x] 4.2 Implement `RunReport.to_json()` and a `print_report(report)` function for the human-readable stdout form
- [x] 4.3 Implement `write_report(report, workdir)` that writes `run-report.json` and returns the path
- [x] 4.4 Unit-test that no required field can be empty/None when building from a successful run
- [x] 4.5 Unit-test that `tokens.total == tokens.prompt + tokens.completion` is enforced (or asserted) during construction

## 5. CLI wiring

- [x] 5.1 In `agent/cli.py`, implement `main(argv=None)` with argparse: positional `goal`, optional `--workdir`, optional `--model`
- [x] 5.2 Resolve workdir: use `--workdir` if given, else create `./.agent-runs/<UTC-timestamp>/`; create directory eagerly
- [x] 5.3 Instantiate `MoonshotClient`, call `complete([{role: "user", content: goal}])`, persist the assistant content to `<workdir>/llm-response.txt`
- [x] 5.4 Build a `RunReport` (`outcome="success"`, `iterations=1`, real token usage, real artifact paths), print it, and write `run-report.json`
- [x] 5.5 Wrap the run in error handling: missing API key, network error, non-success provider response → print one-line stderr error, write a `run-report.json` with `outcome="failure"`, exit non-zero
- [x] 5.6 Wire `agent/__main__.py` to call `cli.main()`

## 6. End-to-end verification

- [x] 6.1 Add a unit-level CLI test that injects a `FakeLLMClient`, runs `main()` against a tmp workdir, and asserts the report has every required field populated and `iterations == 1`
- [x] 6.2 Add a CLI test for the missing-API-key path: assert non-zero exit, stderr message, and a failure `run-report.json` written to the workdir
- [x] 6.3 Run a manual smoke test: `MOONSHOT_API_KEY=... agent "write add(a,b) with a passing test"` — confirm stdout report and `run-report.json` are populated with real token counts and resolvable artifact paths
- [x] 6.4 Confirm phase done-criteria from `phases.md` Phase 1: report contains no `"unknown"` fields and a real Moonshot token count

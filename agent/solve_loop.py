from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from agent.extract import ExtractionError, extract
from agent.failure_memory import (
    FailureEntry,
    FailureMemoryWriter,
    SCHEMA_VERSION,
    now_utc_iso,
    resolve_persistent_root,
    truncate_excerpt,
)
from agent.llm.client import LLMClient, TokenUsage
from agent import memory_retrieval, success_memory
from agent.prompting import build_generate_prompt, build_reflect_prompt, render_prior_context_block
from agent.reflection import (
    Reflection,
    StructuredReflection,
    head,
    parse_structured_reflection,
    tail,
)
from agent.report import IterationEntry
from agent.sandbox import PathEscapeError, Sandbox, SandboxResult


@dataclass
class SolveConfig:
    max_iterations: int = 5
    cpu_seconds: int = 10
    wall_seconds: float = 15.0


@dataclass
class RunResult:
    outcome: str  # "success" | "failure" | "gave_up"
    iterations: int
    iteration_log: list[IterationEntry]
    tokens: TokenUsage
    model: str
    run_id: str = ""
    failure_persistent_paths: list[str] = field(default_factory=list)
    failure_workdir_paths: list[str] = field(default_factory=list)
    retrieved_failures: list[dict] = field(default_factory=list)
    retrieved_successes: list[dict] = field(default_factory=list)
    success_entry_path: Optional[str] = None

    @property
    def success(self) -> bool:
        return self.outcome == "success"


SandboxFactory = Callable[[], Sandbox]


def run(
    *,
    goal: str,
    config: SolveConfig,
    llm_client: LLMClient,
    workdir: Path,
    sandbox_factory: Optional[SandboxFactory] = None,
    model: Optional[str] = None,
    run_id: Optional[str] = None,
    persistent_root: Optional[Path] = None,
) -> RunResult:
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")

    sandbox_factory = sandbox_factory or (lambda: Sandbox())
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    run_id = run_id or uuid.uuid4().hex
    persistent_root = Path(persistent_root) if persistent_root else resolve_persistent_root()
    failure_writer = FailureMemoryWriter(persistent_root, workdir, run_id=run_id)

    retrieval = memory_retrieval.retrieve(goal, persistent_root)
    retrieved_failure_payloads = [r.payload for r in retrieval.failures]
    retrieved_success_payloads = [r.payload for r in retrieval.successes]
    prior_context_block = render_prior_context_block(
        retrieved_failure_payloads, retrieved_success_payloads
    )

    def _refs_to_dicts(refs) -> list[dict]:
        return [{"path": r.path, "run_id": r.run_id, "score": r.score} for r in refs]

    retrieved_failures_meta = _refs_to_dicts(retrieval.failures)
    retrieved_successes_meta = _refs_to_dicts(retrieval.successes)

    reflections: list[Reflection] = []
    iteration_log: list[IterationEntry] = []
    last_model = model or ""
    total_prompt = 0
    total_completion = 0
    success_entry_path: Optional[str] = None
    last_extracted_code = ""
    last_extracted_tests = ""

    def _build_result(outcome: str, iters: int) -> RunResult:
        return RunResult(
            outcome=outcome,
            iterations=iters,
            iteration_log=iteration_log,
            tokens=_usage(total_prompt, total_completion),
            model=last_model,
            run_id=run_id,
            failure_persistent_paths=[str(p.resolve()) for p in failure_writer.persistent_paths],
            failure_workdir_paths=[str(p.resolve()) for p in failure_writer.workdir_paths],
            retrieved_failures=retrieved_failures_meta,
            retrieved_successes=retrieved_successes_meta,
            success_entry_path=success_entry_path,
        )

    for i in range(1, config.max_iterations + 1):
        iter_dir = workdir / f"iter-{i}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        iter_prompt_tokens = 0
        iter_completion_tokens = 0
        artifacts: dict[str, str] = {}

        # 1. Generate
        iter_prior_context = prior_context_block if i == 1 else ""
        gen_messages = build_generate_prompt(goal, reflections, iter_prior_context)
        gen_resp = llm_client.complete(gen_messages, model=model)
        last_model = gen_resp.model or last_model
        iter_prompt_tokens += gen_resp.usage.prompt
        iter_completion_tokens += gen_resp.usage.completion

        raw_path = iter_dir / "model_response.txt"
        raw_path.write_text(gen_resp.content, encoding="utf-8")
        artifacts["model_response"] = str(raw_path.resolve())

        # 2. Extract
        try:
            extracted = extract(gen_resp.content)
        except ExtractionError as e:
            summary = f"could not parse model output: {e}"
            structured = StructuredReflection(
                error_type="ExtractionError",
                root_cause_summary=summary,
                code_or_assumptions="model output did not contain two python code blocks",
                next_hypothesis="re-emit two ```python blocks for solution and tests",
            )
            reflections.append(
                Reflection(
                    iteration=i,
                    code_excerpt="",
                    pytest_exit_code=None,
                    stdout_tail="",
                    stderr_tail="",
                    summary=summary,
                )
            )
            _persist_failure(
                failure_writer,
                run_id=run_id,
                iteration=i,
                goal=goal,
                structured=structured,
                pytest_excerpt="",
            )
            mirror = failure_writer.workdir_mirror(i)
            artifacts["failure_entry"] = str(mirror.resolve())
            iteration_log.append(
                IterationEntry(
                    index=i,
                    outcome="failure",
                    tokens=_usage(iter_prompt_tokens, iter_completion_tokens),
                    artifacts=artifacts,
                )
            )
            total_prompt += iter_prompt_tokens
            total_completion += iter_completion_tokens
            continue

        code_path = iter_dir / "code.py"
        tests_path = iter_dir / "test_code.py"
        code_path.write_text(extracted.code, encoding="utf-8")
        tests_path.write_text(extracted.tests, encoding="utf-8")
        last_extracted_code = extracted.code
        last_extracted_tests = extracted.tests
        artifacts["code"] = str(code_path.resolve())
        artifacts["tests"] = str(tests_path.resolve())

        # 3. Sandbox-run pytest
        sandbox_result: SandboxResult
        path_escape_error: Optional[str] = None
        try:
            with sandbox_factory() as sb:
                try:
                    sb.write_file("solution.py", extracted.code)
                    sb.write_file("test_solution.py", extracted.tests)
                except PathEscapeError as e:
                    path_escape_error = str(e)
                    sandbox_result = SandboxResult(
                        exit_code=None,
                        stdout="",
                        stderr=path_escape_error,
                        killed=False,
                        duration_seconds=0.0,
                    )
                else:
                    sandbox_result = sb.run_pytest(
                        cpu_seconds=config.cpu_seconds,
                        wall_seconds=config.wall_seconds,
                    )
        except Exception as e:
            sandbox_result = SandboxResult(
                exit_code=None,
                stdout="",
                stderr=f"sandbox exception: {type(e).__name__}: {e}",
                killed=False,
                duration_seconds=0.0,
            )

        stdout_path = iter_dir / "pytest.stdout"
        stderr_path = iter_dir / "pytest.stderr"
        stdout_path.write_text(sandbox_result.stdout, encoding="utf-8")
        stderr_path.write_text(sandbox_result.stderr, encoding="utf-8")
        artifacts["pytest_stdout"] = str(stdout_path.resolve())
        artifacts["pytest_stderr"] = str(stderr_path.resolve())

        # 4. Determine iteration outcome
        if path_escape_error is not None:
            iter_outcome = "failure"
            summary = f"filesystem escape rejected: {path_escape_error}"
            default_error_type = "PathEscape"
        elif sandbox_result.killed:
            iter_outcome = "sandbox_killed"
            summary = "killed by sandbox (wall-clock limit exceeded)"
            default_error_type = "SandboxTimeout"
        elif sandbox_result.exit_code == 0:
            iter_outcome = "success"
            summary = "tests passed"
            default_error_type = ""
        else:
            iter_outcome = "failure"
            summary = f"pytest failed (exit_code={sandbox_result.exit_code})"
            default_error_type = "TestFailure"

        # 5. Reflect on failure (LLM call) — skip on success
        if iter_outcome != "success":
            try:
                refl_messages = build_reflect_prompt(
                    goal,
                    extracted.code,
                    extracted.tests,
                    tail(sandbox_result.stdout + "\n" + sandbox_result.stderr, 3000),
                )
                refl_resp = llm_client.complete(refl_messages, model=model)
                iter_prompt_tokens += refl_resp.usage.prompt
                iter_completion_tokens += refl_resp.usage.completion
                last_model = refl_resp.model or last_model
                structured = parse_structured_reflection(refl_resp.content or "")
                summary = (structured.root_cause_summary or summary).strip() or summary
            except Exception as e:
                summary = f"{summary}; reflection call failed: {type(e).__name__}: {e}"
                structured = StructuredReflection(
                    error_type=default_error_type or "ReflectionCallFailed",
                    root_cause_summary=summary,
                    code_or_assumptions=head(extracted.code) or "n/a",
                    next_hypothesis="retry with corrected approach",
                )

            reflections.append(
                Reflection(
                    iteration=i,
                    code_excerpt=head(extracted.code),
                    pytest_exit_code=sandbox_result.exit_code,
                    stdout_tail=tail(sandbox_result.stdout, 1500),
                    stderr_tail=tail(sandbox_result.stderr, 1500),
                    summary=summary,
                )
            )

            pytest_excerpt = (sandbox_result.stdout or "") + (
                ("\n" + sandbox_result.stderr) if sandbox_result.stderr else ""
            )
            _persist_failure(
                failure_writer,
                run_id=run_id,
                iteration=i,
                goal=goal,
                structured=structured,
                pytest_excerpt=pytest_excerpt,
            )
            mirror = failure_writer.workdir_mirror(i)
            artifacts["failure_entry"] = str(mirror.resolve())

        iteration_log.append(
            IterationEntry(
                index=i,
                outcome=iter_outcome,  # type: ignore[arg-type]
                tokens=_usage(iter_prompt_tokens, iter_completion_tokens),
                artifacts=artifacts,
            )
        )
        total_prompt += iter_prompt_tokens
        total_completion += iter_completion_tokens

        if iter_outcome == "success":
            try:
                sp = success_memory.write(
                    run_id=run_id,
                    goal=goal,
                    solution_code=last_extracted_code or "(empty)",
                    tests=last_extracted_tests or "(empty)",
                    iterations=i,
                    model=last_model or "unknown",
                    root=persistent_root,
                )
                success_entry_path = str(sp.resolve())
            except Exception as e:
                # A green run shouldn't be failed by a memory-persistence hiccup;
                # surface the error in the iteration's artifacts instead.
                artifacts["success_entry_error"] = f"{type(e).__name__}: {e}"
            return _build_result("success", i)

    return _build_result("gave_up", config.max_iterations)


def _persist_failure(
    writer: FailureMemoryWriter,
    *,
    run_id: str,
    iteration: int,
    goal: str,
    structured: StructuredReflection,
    pytest_excerpt: str,
) -> None:
    entry = FailureEntry(
        schema_version=SCHEMA_VERSION,
        run_id=run_id,
        iteration=iteration,
        timestamp=now_utc_iso(),
        goal=goal,
        error_type=structured.error_type or "Unknown",
        root_cause_summary=structured.root_cause_summary or "(no summary)",
        code_or_assumptions=structured.code_or_assumptions or "n/a",
        next_hypothesis=structured.next_hypothesis or "retry",
        failing_test_excerpt=truncate_excerpt(pytest_excerpt) or "(no output)",
    )
    writer.write(entry)


def _usage(prompt: int, completion: int) -> TokenUsage:
    return TokenUsage(prompt=prompt, completion=completion, total=prompt + completion)

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

from agent.extract import ExtractionError, extract
from agent.llm.client import LLMClient, TokenUsage
from agent.prompting import build_generate_prompt, build_reflect_prompt
from agent.reflection import Reflection, head, tail
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
) -> RunResult:
    if config.max_iterations < 1:
        raise ValueError("max_iterations must be >= 1")

    sandbox_factory = sandbox_factory or (lambda: Sandbox())
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)

    reflections: list[Reflection] = []
    iteration_log: list[IterationEntry] = []
    last_model = model or ""
    total_prompt = 0
    total_completion = 0

    for i in range(1, config.max_iterations + 1):
        iter_dir = workdir / f"iter-{i}"
        iter_dir.mkdir(parents=True, exist_ok=True)
        iter_prompt_tokens = 0
        iter_completion_tokens = 0
        artifacts: dict[str, str] = {}

        # 1. Generate
        gen_messages = build_generate_prompt(goal, reflections)
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
        elif sandbox_result.killed:
            iter_outcome = "sandbox_killed"
            summary = "killed by sandbox (wall-clock limit exceeded)"
        elif sandbox_result.exit_code == 0:
            iter_outcome = "success"
            summary = "tests passed"
        else:
            iter_outcome = "failure"
            summary = f"pytest failed (exit_code={sandbox_result.exit_code})"

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
                summary = (refl_resp.content or summary).strip() or summary
            except Exception as e:
                summary = f"{summary}; reflection call failed: {type(e).__name__}: {e}"

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
            return RunResult(
                outcome="success",
                iterations=i,
                iteration_log=iteration_log,
                tokens=_usage(total_prompt, total_completion),
                model=last_model,
            )

    return RunResult(
        outcome="gave_up",
        iterations=config.max_iterations,
        iteration_log=iteration_log,
        tokens=_usage(total_prompt, total_completion),
        model=last_model,
    )


def _usage(prompt: int, completion: int) -> TokenUsage:
    return TokenUsage(prompt=prompt, completion=completion, total=prompt + completion)

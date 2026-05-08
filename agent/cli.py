from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agent import solve_loop
from agent.llm.client import LLMClient, TokenUsage
from agent.report import RunReport, print_report, write_report

DEFAULT_MAX_ITERATIONS = 5


def _load_dotenv() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _default_workdir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path.cwd() / ".agent-runs" / stamp


def _positive_int(raw: str) -> int:
    try:
        v = int(raw)
    except (TypeError, ValueError):
        raise argparse.ArgumentTypeError(f"must be a positive integer, got {raw!r}")
    if v < 1:
        raise argparse.ArgumentTypeError(f"must be >= 1, got {v}")
    return v


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent", description="Self-improving coding agent.")
    p.add_argument("goal", help="Natural-language coding task for the agent.")
    p.add_argument("--workdir", default=None, help="Directory for run artifacts (default: ./.agent-runs/<utc-timestamp>/).")
    p.add_argument("--model", default=None, help="Override the Moonshot model name.")
    p.add_argument(
        "--max-iterations",
        type=_positive_int,
        default=DEFAULT_MAX_ITERATIONS,
        help=f"Circuit-breaker cap on solve-loop iterations (default: {DEFAULT_MAX_ITERATIONS}).",
    )
    return p


def _make_default_client(model: str | None) -> tuple[LLMClient, str]:
    from agent.llm.moonshot import MoonshotClient

    client = MoonshotClient()
    return client, model or client.default_model


def main(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[[str | None], tuple[LLMClient, str]] | None = None,
    sandbox_factory=None,
) -> int:
    _load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)

    workdir = Path(args.workdir) if args.workdir else _default_workdir()
    workdir.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now_iso()
    run_report_path = workdir / "run-report.json"

    factory = client_factory or _make_default_client
    model_used = args.model or "unset"

    try:
        client, model_used = factory(args.model)
        result = solve_loop.run(
            goal=args.goal,
            config=solve_loop.SolveConfig(max_iterations=args.max_iterations),
            llm_client=client,
            workdir=workdir,
            sandbox_factory=sandbox_factory,
            model=args.model,
        )
        model_used = result.model or model_used
        report = RunReport(
            goal=args.goal,
            outcome=result.outcome,  # type: ignore[arg-type]
            iterations=result.iterations,
            tokens=result.tokens,
            model=model_used,
            artifacts={
                "workdir": str(workdir.resolve()),
                "run_report": str(run_report_path.resolve()),
            },
            started_at=started_at,
            finished_at=_utc_now_iso(),
            max_iterations=args.max_iterations,
            iteration_log=result.iteration_log,
        )
        write_report(report, workdir)
        print_report(report)
        if result.outcome == "success":
            return 0
        if result.outcome == "gave_up":
            print(f"agent: gave up after {result.iterations} iterations", file=sys.stderr)
            return 2
        return 1
    except Exception as exc:
        print(f"agent: {type(exc).__name__}: {exc}", file=sys.stderr)
        try:
            failure = RunReport(
                goal=args.goal,
                outcome="failure",
                iterations=1,
                tokens=TokenUsage(prompt=0, completion=0, total=0),
                model=model_used or "unset",
                artifacts={
                    "workdir": str(workdir.resolve()),
                    "run_report": str(run_report_path.resolve()),
                    "error": f"{type(exc).__name__}: {exc}",
                },
                started_at=started_at,
                finished_at=_utc_now_iso(),
                max_iterations=args.max_iterations,
            )
            write_report(failure, workdir)
        except Exception as report_exc:
            print(f"agent: failed to write failure report: {report_exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

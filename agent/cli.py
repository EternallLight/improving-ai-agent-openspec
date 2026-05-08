from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from agent.llm.client import LLMClient, Message, TokenUsage
from agent.report import RunReport, print_report, write_report


def _load_dotenv() -> None:
    try:
        from dotenv import find_dotenv, load_dotenv
    except ImportError:
        return
    # Search from CWD upward (not from this file's location), so tests that
    # chdir to a clean tmp dir won't pick up the repo's .env.
    path = find_dotenv(usecwd=True)
    if path:
        load_dotenv(path, override=False)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


def _default_workdir() -> Path:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    return Path.cwd() / ".agent-runs" / stamp


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="agent", description="Self-improving coding agent.")
    p.add_argument("goal", help="Natural-language coding task for the agent.")
    p.add_argument("--workdir", default=None, help="Directory for run artifacts (default: ./.agent-runs/<utc-timestamp>/).")
    p.add_argument("--model", default=None, help="Override the Moonshot model name.")
    return p


def _make_default_client(model: str | None) -> tuple[LLMClient, str]:
    from agent.llm.moonshot import MoonshotClient

    client = MoonshotClient()
    return client, model or client.default_model


def main(
    argv: list[str] | None = None,
    *,
    client_factory: Callable[[str | None], tuple[LLMClient, str]] | None = None,
) -> int:
    _load_dotenv()
    parser = _build_parser()
    args = parser.parse_args(argv)

    workdir = Path(args.workdir) if args.workdir else _default_workdir()
    workdir.mkdir(parents=True, exist_ok=True)
    started_at = _utc_now_iso()

    factory = client_factory or _make_default_client
    model_used = args.model or "unset"

    try:
        client, model_used = factory(args.model)
        response = client.complete(
            [Message(role="user", content=args.goal)],
            model=args.model,
        )
        model_used = response.model or model_used
        llm_response_path = workdir / "llm-response.txt"
        llm_response_path.write_text(response.content, encoding="utf-8")

        run_report_path = workdir / "run-report.json"
        report = RunReport(
            goal=args.goal,
            outcome="success",
            iterations=1,
            tokens=response.usage,
            model=model_used,
            artifacts={
                "workdir": str(workdir.resolve()),
                "run_report": str(run_report_path.resolve()),
                "llm_response": str(llm_response_path.resolve()),
            },
            started_at=started_at,
            finished_at=_utc_now_iso(),
        )
        write_report(report, workdir)
        print_report(report)
        return 0
    except Exception as exc:
        print(f"agent: {type(exc).__name__}: {exc}", file=sys.stderr)
        run_report_path = workdir / "run-report.json"
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
            )
            write_report(failure, workdir)
        except Exception as report_exc:
            print(f"agent: failed to write failure report: {report_exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

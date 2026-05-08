from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from agent.llm.client import TokenUsage

Outcome = Literal["success", "failure", "gave_up"]


@dataclass
class RunReport:
    goal: str
    outcome: Outcome
    iterations: int
    tokens: TokenUsage
    model: str
    artifacts: dict[str, str]
    started_at: str
    finished_at: str

    def __post_init__(self) -> None:
        missing = []
        if not self.goal:
            missing.append("goal")
        if not self.outcome:
            missing.append("outcome")
        if not self.model:
            missing.append("model")
        if not self.started_at:
            missing.append("started_at")
        if not self.finished_at:
            missing.append("finished_at")
        if not self.artifacts:
            missing.append("artifacts")
        else:
            for k in ("workdir", "run_report"):
                if k not in self.artifacts or not self.artifacts[k]:
                    missing.append(f"artifacts.{k}")
        if self.iterations is None or self.iterations < 1:
            missing.append("iterations")
        if missing:
            raise ValueError(f"run report missing required fields: {', '.join(missing)}")
        if self.tokens.total != self.tokens.prompt + self.tokens.completion:
            raise ValueError("tokens.total must equal prompt + completion")

    def to_dict(self) -> dict:
        d = asdict(self)
        d["tokens"] = {
            "prompt": self.tokens.prompt,
            "completion": self.tokens.completion,
            "total": self.tokens.total,
        }
        return d

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def print_report(report: RunReport) -> None:
    d = report.to_dict()
    lines = [
        "=== Agent Run Report ===",
        f"goal:        {d['goal']}",
        f"outcome:     {d['outcome']}",
        f"iterations:  {d['iterations']}",
        f"model:       {d['model']}",
        f"tokens:      prompt={d['tokens']['prompt']} completion={d['tokens']['completion']} total={d['tokens']['total']}",
        f"started_at:  {d['started_at']}",
        f"finished_at: {d['finished_at']}",
        "artifacts:",
    ]
    for k, v in d["artifacts"].items():
        lines.append(f"  {k}: {v}")
    print("\n".join(lines))


def write_report(report: RunReport, workdir: Path | str) -> Path:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / "run-report.json"
    path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path

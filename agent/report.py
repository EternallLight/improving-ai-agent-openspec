from __future__ import annotations

import json
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Literal

from agent.llm.client import TokenUsage

Outcome = Literal["success", "failure", "gave_up"]
IterationOutcome = Literal["success", "failure", "sandbox_killed"]


@dataclass
class IterationEntry:
    index: int
    outcome: IterationOutcome
    tokens: TokenUsage
    artifacts: dict[str, str]

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "outcome": self.outcome,
            "tokens": {
                "prompt": self.tokens.prompt,
                "completion": self.tokens.completion,
                "total": self.tokens.total,
            },
            "artifacts": dict(self.artifacts),
        }


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
    max_iterations: int = 1
    iteration_log: list[IterationEntry] = field(default_factory=list)
    failure_entries: dict = field(
        default_factory=lambda: {"count": 0, "persistent_paths": [], "workdir_paths": []}
    )

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
        if self.max_iterations is None or self.max_iterations < 1:
            missing.append("max_iterations")
        if missing:
            raise ValueError(f"run report missing required fields: {', '.join(missing)}")
        if self.tokens.total != self.tokens.prompt + self.tokens.completion:
            raise ValueError("tokens.total must equal prompt + completion")
        if self.iteration_log:
            sum_total = sum(e.tokens.total for e in self.iteration_log)
            if sum_total != self.tokens.total:
                raise ValueError(
                    f"top-level tokens.total ({self.tokens.total}) must equal sum of iteration tokens ({sum_total})"
                )

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "outcome": self.outcome,
            "iterations": self.iterations,
            "max_iterations": self.max_iterations,
            "tokens": {
                "prompt": self.tokens.prompt,
                "completion": self.tokens.completion,
                "total": self.tokens.total,
            },
            "model": self.model,
            "artifacts": dict(self.artifacts),
            "started_at": self.started_at,
            "finished_at": self.finished_at,
            "iteration_log": [e.to_dict() for e in self.iteration_log],
            "failure_entries": {
                "count": int(self.failure_entries.get("count", 0)),
                "persistent_paths": list(self.failure_entries.get("persistent_paths", [])),
                "workdir_paths": list(self.failure_entries.get("workdir_paths", [])),
            },
        }

    def to_json(self, *, indent: int = 2) -> str:
        return json.dumps(self.to_dict(), indent=indent, sort_keys=True)


def print_report(report: RunReport) -> None:
    d = report.to_dict()
    lines = [
        "=== Agent Run Report ===",
        f"goal:           {d['goal']}",
        f"outcome:        {d['outcome']}",
        f"iterations:     {d['iterations']} / {d['max_iterations']}",
        f"model:          {d['model']}",
        f"tokens:         prompt={d['tokens']['prompt']} completion={d['tokens']['completion']} total={d['tokens']['total']}",
        f"started_at:     {d['started_at']}",
        f"finished_at:    {d['finished_at']}",
        "artifacts:",
    ]
    for k, v in d["artifacts"].items():
        lines.append(f"  {k}: {v}")
    if d["iteration_log"]:
        lines.append("iterations:")
        for e in d["iteration_log"]:
            lines.append(
                f"  [{e['index']}] outcome={e['outcome']} tokens={e['tokens']['total']}"
            )
    fe = d.get("failure_entries", {"count": 0, "persistent_paths": []})
    lines.append(f"failure_entries: count={fe['count']}")
    for p in fe.get("persistent_paths", []):
        lines.append(f"  persistent: {p}")
    print("\n".join(lines))


def write_report(report: RunReport, workdir: Path | str) -> Path:
    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    path = workdir / "run-report.json"
    path.write_text(report.to_json() + "\n", encoding="utf-8")
    return path

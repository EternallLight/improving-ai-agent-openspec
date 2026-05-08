from __future__ import annotations

import json
import math
import os
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from agent.failure_memory import resolve_persistent_root

DEFAULT_K_FAILURES = 3
DEFAULT_K_SUCCESSES = 2
DEFAULT_THRESHOLD = 0.1

_TOKEN_RE = re.compile(r"[a-z0-9]+")


@dataclass(frozen=True)
class Ref:
    path: str
    run_id: str
    score: float
    payload: dict


@dataclass
class RetrievalResult:
    failures: list[Ref] = field(default_factory=list)
    successes: list[Ref] = field(default_factory=list)


def _tokenize(text: str) -> list[str]:
    return _TOKEN_RE.findall((text or "").lower())


def _failure_doc(entry: dict) -> str:
    return " ".join(
        [
            entry.get("goal", "") or "",
            entry.get("root_cause_summary", "") or "",
            entry.get("next_hypothesis", "") or "",
        ]
    )


def _success_doc(entry: dict) -> str:
    return entry.get("goal", "") or ""


def _load_failures(root: Path) -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    failures_dir = root / "failures"
    if not failures_dir.is_dir():
        return out
    for f in sorted(failures_dir.glob("*.jsonl")):
        try:
            text = f.read_text(encoding="utf-8")
        except OSError as e:
            print(f"memory_retrieval: skip {f}: {e}", file=sys.stderr)
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
                if not isinstance(entry, dict) or not entry.get("run_id") or not entry.get("goal"):
                    raise ValueError("missing run_id/goal")
            except (json.JSONDecodeError, ValueError) as e:
                print(f"memory_retrieval: skip {f}:{lineno}: {e}", file=sys.stderr)
                continue
            out.append((f, entry))
    return out


def _load_successes(root: Path) -> list[tuple[Path, dict]]:
    out: list[tuple[Path, dict]] = []
    succ_dir = root / "successes"
    if not succ_dir.is_dir():
        return out
    for f in sorted(succ_dir.glob("*.json")):
        try:
            entry = json.loads(f.read_text(encoding="utf-8"))
            if not isinstance(entry, dict) or not entry.get("run_id") or not entry.get("goal"):
                raise ValueError("missing run_id/goal")
        except (OSError, json.JSONDecodeError, ValueError) as e:
            print(f"memory_retrieval: skip {f}: {e}", file=sys.stderr)
            continue
        out.append((f, entry))
    return out


def _tfidf_cosine(query_tokens: list[str], docs: list[list[str]]) -> list[float]:
    """Score each doc against query using TF-IDF cosine. Document frequency is
    computed over the candidate corpus + the query as one extra doc."""
    if not docs:
        return []
    n = len(docs) + 1  # include query in DF
    df: dict[str, int] = {}
    for tokens in docs + [query_tokens]:
        for t in set(tokens):
            df[t] = df.get(t, 0) + 1

    def idf(t: str) -> float:
        return math.log((1 + n) / (1 + df.get(t, 0))) + 1.0

    def vec(tokens: list[str]) -> dict[str, float]:
        if not tokens:
            return {}
        tf: dict[str, int] = {}
        for t in tokens:
            tf[t] = tf.get(t, 0) + 1
        return {t: c * idf(t) for t, c in tf.items()}

    def norm(v: dict[str, float]) -> float:
        return math.sqrt(sum(x * x for x in v.values()))

    qv = vec(query_tokens)
    qn = norm(qv)
    if qn == 0:
        return [0.0] * len(docs)
    scores: list[float] = []
    for tokens in docs:
        dv = vec(tokens)
        dn = norm(dv)
        if dn == 0:
            scores.append(0.0)
            continue
        common = set(qv) & set(dv)
        dot = sum(qv[t] * dv[t] for t in common)
        scores.append(dot / (qn * dn))
    return scores


def _env_int(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        v = int(raw)
        return v if v >= 0 else default
    except ValueError:
        return default


def _env_float(name: str, default: float) -> float:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return float(raw)
    except ValueError:
        return default


def _select(
    candidates: list[tuple[Path, dict]],
    doc_text: list[str],
    query: str,
    k: int,
    threshold: float,
) -> list[Ref]:
    if k <= 0 or not candidates:
        return []
    query_tokens = _tokenize(query)
    docs = [_tokenize(t) for t in doc_text]
    scores = _tfidf_cosine(query_tokens, docs)
    rows: list[tuple[float, str, str, Path, dict]] = []
    for (path, entry), score in zip(candidates, scores):
        if score < threshold:
            continue
        ts = entry.get("timestamp", "") or ""
        rid = entry.get("run_id", "") or ""
        rows.append((score, ts, rid, path, entry))
    # Sort: score desc → timestamp desc → run_id asc.
    # Sort by run_id ascending first, then by (score, timestamp) descending: stable
    # sort means run_id order is preserved within score+timestamp ties.
    rows.sort(key=lambda r: r[2])
    rows.sort(key=lambda r: (r[0], r[1]), reverse=True)
    out: list[Ref] = []
    for score, _ts, rid, path, entry in rows[:k]:
        out.append(Ref(path=str(path), run_id=rid, score=float(score), payload=entry))
    return out


def retrieve(
    new_goal: str,
    root: Optional[Path] = None,
    *,
    k_failures: Optional[int] = None,
    k_successes: Optional[int] = None,
    threshold: Optional[float] = None,
) -> RetrievalResult:
    r = Path(root) if root else resolve_persistent_root()
    kf = k_failures if k_failures is not None else _env_int("AGENT_RETRIEVAL_K_FAILURES", DEFAULT_K_FAILURES)
    ks = k_successes if k_successes is not None else _env_int("AGENT_RETRIEVAL_K_SUCCESSES", DEFAULT_K_SUCCESSES)
    th = threshold if threshold is not None else _env_float("AGENT_RETRIEVAL_THRESHOLD", DEFAULT_THRESHOLD)

    failures = _load_failures(r)
    successes = _load_successes(r)

    failure_refs = _select(failures, [_failure_doc(e) for _, e in failures], new_goal, kf, th)
    success_refs = _select(successes, [_success_doc(e) for _, e in successes], new_goal, ks, th)
    return RetrievalResult(failures=failure_refs, successes=success_refs)

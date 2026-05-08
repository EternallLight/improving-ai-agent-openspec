from __future__ import annotations

import json
import re
from dataclasses import dataclass


@dataclass(frozen=True)
class Reflection:
    iteration: int
    code_excerpt: str
    pytest_exit_code: int | None
    stdout_tail: str
    stderr_tail: str
    summary: str


@dataclass(frozen=True)
class StructuredReflection:
    error_type: str
    root_cause_summary: str
    code_or_assumptions: str
    next_hypothesis: str


def tail(text: str, max_chars: int = 2000) -> str:
    if not text:
        return ""
    if len(text) <= max_chars:
        return text
    return "...[truncated]...\n" + text[-max_chars:]


def head(text: str, max_chars: int = 600) -> str:
    if not text or len(text) <= max_chars:
        return text
    return text[:max_chars] + "\n...[truncated]"


_JSON_FENCE_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL | re.IGNORECASE)
_FALLBACK_OBJ_RE = re.compile(r"(\{.*\})", re.DOTALL)


def parse_structured_reflection(raw: str) -> StructuredReflection:
    """Parse the LLM's structured reflection output.

    Returns a `StructuredReflection`. On any parse failure, returns a
    fallback with `error_type = "ParseError"` and the raw output (truncated)
    as `root_cause_summary`.
    """
    text = (raw or "").strip()
    candidate = None
    m = _JSON_FENCE_RE.search(text)
    if m:
        candidate = m.group(1)
    else:
        m2 = _FALLBACK_OBJ_RE.search(text)
        if m2:
            candidate = m2.group(1)

    if candidate:
        try:
            obj = json.loads(candidate)
            if isinstance(obj, dict):
                fields = {
                    "error_type": str(obj.get("error_type", "")).strip(),
                    "root_cause_summary": str(obj.get("root_cause_summary", "")).strip(),
                    "code_or_assumptions": str(obj.get("code_or_assumptions", "")).strip(),
                    "next_hypothesis": str(obj.get("next_hypothesis", "")).strip(),
                }
                if all(fields.values()):
                    return StructuredReflection(**fields)
        except (json.JSONDecodeError, TypeError):
            pass

    snippet = text if len(text) <= 1500 else text[:1500] + "\n...[truncated]"
    return StructuredReflection(
        error_type="ParseError",
        root_cause_summary=snippet or "empty reflection output",
        code_or_assumptions="unavailable (reflection unparseable)",
        next_hypothesis="retry with corrected approach",
    )

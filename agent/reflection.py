from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Reflection:
    iteration: int
    code_excerpt: str
    pytest_exit_code: int | None
    stdout_tail: str
    stderr_tail: str
    summary: str


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

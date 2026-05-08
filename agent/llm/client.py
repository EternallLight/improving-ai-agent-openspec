from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable


@dataclass(frozen=True)
class Message:
    role: str
    content: str


@dataclass(frozen=True)
class TokenUsage:
    prompt: int
    completion: int
    total: int

    def __post_init__(self) -> None:
        if self.prompt < 0 or self.completion < 0 or self.total < 0:
            raise ValueError("token counts must be non-negative")
        if self.total != self.prompt + self.completion:
            raise ValueError(
                f"total ({self.total}) must equal prompt ({self.prompt}) + completion ({self.completion})"
            )


@dataclass(frozen=True)
class LLMResponse:
    content: str
    usage: TokenUsage
    model: str


@runtime_checkable
class LLMClient(Protocol):
    def complete(
        self,
        messages: list[Message] | list[dict],
        *,
        model: str | None = None,
    ) -> LLMResponse: ...

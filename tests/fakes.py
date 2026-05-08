from __future__ import annotations

from agent.llm.client import LLMResponse, Message, TokenUsage


class FakeLLMClient:
    def __init__(
        self,
        *,
        content: str = "ok",
        prompt_tokens: int = 3,
        completion_tokens: int = 5,
        model: str = "fake-model",
        responses: list[str] | None = None,
    ) -> None:
        self._content = content
        self._prompt = prompt_tokens
        self._completion = completion_tokens
        self._model = model
        self._responses = list(responses) if responses else None
        self.calls: list[dict] = []

    def complete(
        self,
        messages: list[Message] | list[dict],
        *,
        model: str | None = None,
    ) -> LLMResponse:
        self.calls.append({"messages": messages, "model": model})
        chosen = model or self._model
        if self._responses is not None:
            idx = min(len(self.calls) - 1, len(self._responses) - 1)
            content = self._responses[idx]
        else:
            content = self._content
        return LLMResponse(
            content=content,
            usage=TokenUsage(
                prompt=self._prompt,
                completion=self._completion,
                total=self._prompt + self._completion,
            ),
            model=chosen,
        )

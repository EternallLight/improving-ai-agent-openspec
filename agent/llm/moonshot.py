from __future__ import annotations

import os
from typing import Any

from agent.llm.client import LLMResponse, Message, TokenUsage

MOONSHOT_BASE_URL = "https://api.moonshot.ai/v1"
DEFAULT_MODEL = "kimi-k2-0905-preview"


def _resolve_default_model() -> str:
    return os.environ.get("MOONSHOT_MODEL", DEFAULT_MODEL)


def _to_dict(m: Message | dict) -> dict[str, Any]:
    if isinstance(m, Message):
        return {"role": m.role, "content": m.content}
    return dict(m)


class MoonshotClient:
    def __init__(self, *, api_key: str | None = None, base_url: str = MOONSHOT_BASE_URL) -> None:
        key = api_key if api_key is not None else os.environ.get("MOONSHOT_API_KEY")
        if not key:
            raise RuntimeError(
                "MOONSHOT_API_KEY is not set. Export it before invoking the agent."
            )
        from openai import OpenAI

        self._client = OpenAI(api_key=key, base_url=base_url)
        self._default_model = _resolve_default_model()

    @property
    def default_model(self) -> str:
        return self._default_model

    def complete(
        self,
        messages: list[Message] | list[dict],
        *,
        model: str | None = None,
    ) -> LLMResponse:
        chosen_model = model or self._default_model
        payload = [_to_dict(m) for m in messages]
        resp = self._client.chat.completions.create(
            model=chosen_model,
            messages=payload,
        )
        choice = resp.choices[0]
        content = choice.message.content or ""
        usage_obj = resp.usage
        if usage_obj is None:
            raise RuntimeError("Moonshot response missing usage data")
        prompt = int(getattr(usage_obj, "prompt_tokens", 0))
        completion = int(getattr(usage_obj, "completion_tokens", 0))
        total = int(getattr(usage_obj, "total_tokens", prompt + completion))
        if total != prompt + completion:
            total = prompt + completion
        return LLMResponse(
            content=content,
            usage=TokenUsage(prompt=prompt, completion=completion, total=total),
            model=chosen_model,
        )

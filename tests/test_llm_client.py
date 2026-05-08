from __future__ import annotations

from agent.llm.client import LLMClient, LLMResponse, Message, TokenUsage
from tests.fakes import FakeLLMClient


def test_fake_satisfies_protocol_runtime():
    fake = FakeLLMClient()
    assert isinstance(fake, LLMClient)


def test_fake_satisfies_protocol_static():
    client: LLMClient = FakeLLMClient()
    resp = client.complete([Message(role="user", content="hi")])
    assert isinstance(resp, LLMResponse)
    assert resp.content
    assert isinstance(resp.usage, TokenUsage)
    assert resp.usage.total == resp.usage.prompt + resp.usage.completion


def test_token_usage_rejects_inconsistent_total():
    import pytest

    with pytest.raises(ValueError):
        TokenUsage(prompt=1, completion=2, total=4)

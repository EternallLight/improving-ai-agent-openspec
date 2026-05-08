from __future__ import annotations

import os

import pytest

from agent.llm.client import Message
from agent.llm.moonshot import DEFAULT_MODEL, MoonshotClient, _resolve_default_model


def test_missing_api_key_raises(monkeypatch):
    monkeypatch.delenv("MOONSHOT_API_KEY", raising=False)
    with pytest.raises(RuntimeError, match="MOONSHOT_API_KEY"):
        MoonshotClient()


def test_default_model_env_override(monkeypatch):
    monkeypatch.delenv("MOONSHOT_MODEL", raising=False)
    assert _resolve_default_model() == DEFAULT_MODEL
    monkeypatch.setenv("MOONSHOT_MODEL", "kimi-test-model")
    assert _resolve_default_model() == "kimi-test-model"


@pytest.mark.live
def test_live_moonshot_call():
    if not os.environ.get("MOONSHOT_API_KEY"):
        pytest.skip("MOONSHOT_API_KEY not set")
    client = MoonshotClient()
    resp = client.complete([Message(role="user", content="Reply with exactly: pong")])
    assert resp.content.strip()
    assert resp.usage.total > 0
    assert resp.usage.total == resp.usage.prompt + resp.usage.completion

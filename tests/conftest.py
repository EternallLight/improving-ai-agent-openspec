from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def _isolate_agent_memory(tmp_path, monkeypatch):
    """Redirect AGENT_MEMORY_DIR to a per-test tmp dir so tests never touch ~/.agent/memory."""
    monkeypatch.setenv("AGENT_MEMORY_DIR", str(tmp_path / "_agent_memory"))

from __future__ import annotations

import os
import time

import pytest

from agent.sandbox import PathEscapeError, Sandbox


def test_sandbox_creates_and_cleans_scratch():
    with Sandbox() as sb:
        scratch = sb.scratch_dir
        assert scratch.exists()
        assert scratch.is_dir()
    assert not scratch.exists()


def test_write_file_rejects_escape():
    with Sandbox() as sb:
        with pytest.raises(PathEscapeError):
            sb.write_file("../escape.py", "x = 1")
        with pytest.raises(PathEscapeError):
            sb.write_file("/etc/passwd", "x = 1")


def test_write_file_accepts_nested_relative():
    with Sandbox() as sb:
        p = sb.write_file("nested/dir/x.py", "y = 2")
        assert p.read_text() == "y = 2"


def test_run_pytest_passes_when_test_passes():
    with Sandbox() as sb:
        sb.write_file(
            "test_ok.py",
            "def test_ok():\n    assert 1 + 1 == 2\n",
        )
        result = sb.run_pytest(cpu_seconds=5, wall_seconds=15.0)
        assert result.killed is False
        assert result.exit_code == 0


def test_run_pytest_kills_infinite_loop():
    with Sandbox() as sb:
        sb.write_file(
            "test_loop.py",
            "def test_loop():\n    while True:\n        pass\n",
        )
        start = time.monotonic()
        result = sb.run_pytest(cpu_seconds=2, wall_seconds=3.0)
        elapsed = time.monotonic() - start
    assert result.killed is True or result.exit_code not in (0, None)
    assert elapsed < 8.0


def test_run_pytest_fails_when_test_fails():
    with Sandbox() as sb:
        sb.write_file(
            "test_bad.py",
            "def test_bad():\n    assert False\n",
        )
        result = sb.run_pytest(cpu_seconds=5, wall_seconds=15.0)
        assert result.killed is False
        assert result.exit_code not in (0, None)

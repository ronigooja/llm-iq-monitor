import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

from llm_iq_monitor.sandbox import build_command, score_code


def test_command_has_documented_isolation_flags():
    command = build_command("x", "y", "/source", "/tests")
    for flag in ("--rm", "--network", "none", "--read-only", "--cap-drop", "ALL", "--memory", "256m", "--cpus", "0.5", "--pids-limit", "64", "--user", "65534:65534", "python:3.11-slim"):
        assert flag in command


def test_score_code_uses_injected_runner_without_docker():
    calls = []

    async def fake_runner(code, tests):
        calls.append((code, tests))
        return True

    question = type("Question", (), {"meta": {"tests": [{"args": [1], "expected": 1}]}})()
    assert score_code(question, "```python\ndef solve(x):\n return x\n```", fake_runner)
    assert calls and "def solve" in calls[0][0]


def test_score_code_rejects_missing_solution():
    question = type("Question", (), {"meta": {"tests": []}})()
    assert not score_code(question, "plain text", lambda *_: True)

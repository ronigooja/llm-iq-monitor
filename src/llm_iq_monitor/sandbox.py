"""One-shot Docker execution for untrusted model-written solutions."""

from __future__ import annotations

import asyncio
import json
import os
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable


def build_command(source: str, tests: str, source_dir: str, tests_dir: str) -> list[str]:
    return [
        "docker", "run", "--rm", "--network", "none", "--read-only", "--cap-drop", "ALL",
        "--security-opt", "no-new-privileges", "--memory", "256m", "--cpus", "0.5",
        "--pids-limit", "64", "--user", "65534:65534", "--tmpfs", "/tmp:rw,noexec,nosuid,size=32m",
        "-v", f"{source_dir}:/input:ro", "-v", f"{tests_dir}:/tests:ro", "python:3.11-slim",
        "python", "/tests/runner.py", "/input/solution.py", "/tests/tests.json",
    ]


async def run_code(code: str, tests: list, timeout_s: float = 10) -> bool:
    with tempfile.TemporaryDirectory(prefix="llm-iq-sandbox-") as directory:
        root = Path(directory)
        source_dir, tests_dir = root / "source", root / "tests"
        source_dir.mkdir(); tests_dir.mkdir()
        (source_dir / "solution.py").write_text(code, encoding="utf-8")
        (tests_dir / "tests.json").write_text(json.dumps(tests), encoding="utf-8")
        (tests_dir / "runner.py").write_text(_RUNNER, encoding="utf-8")
        command = build_command(code, json.dumps(tests), str(source_dir), str(tests_dir))
        try:
            process = await asyncio.create_subprocess_exec(*command, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                await asyncio.wait_for(process.wait(), timeout=timeout_s)
            except asyncio.TimeoutError:
                process.kill()
                await process.wait()
                return False
            return process.returncode == 0
        except (OSError, asyncio.SubprocessError):
            return False


def score_code(question: Any, reply: str, runner: Callable[..., Any] = run_code) -> bool:
    from .questions.code import extract_code

    code = extract_code(reply)
    if code is None:
        return False
    tests = question.meta.get("tests", [])
    result = runner(code, tests)
    if hasattr(result, "__await__"):
        try:
            result = asyncio.run(result)
        except (RuntimeError, asyncio.CancelledError):
            return False
    return bool(result)


_RUNNER = '''
import importlib.util, json, sys
spec = importlib.util.spec_from_file_location("solution", sys.argv[1])
module = importlib.util.module_from_spec(spec)
spec.loader.exec_module(module)
if not callable(getattr(module, "solve", None)):
    raise SystemExit(1)
with open(sys.argv[2]) as handle:
    tests = json.load(handle)
for test in tests:
    actual = module.solve(*test["args"])
    if actual != test["expected"]:
        raise SystemExit(1)
'''

"""Cross-dimension v2 generation properties: timing, determinism, no assert/raise, UI prompts."""

import ast
import datetime as dt
import time
from pathlib import Path

from llm_iq_monitor.questions import DIM_COUNTS, DIMS, generate

ROOT = Path(__file__).parents[1] / "src" / "llm_iq_monitor" / "questions"


def _daily(start, count):
    first = dt.date.fromisoformat(start)
    return [(first + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(count)]


def test_documented_counts():
    assert {d: DIM_COUNTS[d] for d in DIMS} == {"reasoning": 18, "code": 12, "instruction": 14, "write_zh": 8,
                                                "write_en": 8, "ui": 2}


def test_each_generate_call_is_fast_for_120_daily_seeds():
    slowest = 0.0
    for seed in _daily("2026-01-01", 120):
        for dim in ("reasoning", "code", "instruction", "ui"):
            started = time.perf_counter()
            questions = generate(dim, seed)
            slowest = max(slowest, time.perf_counter() - started)
            assert len(questions) == DIM_COUNTS[dim]
            assert len({q.prompt for q in questions}) == len(questions)
    assert slowest < 3.0


def test_deterministic():
    for dim in ("reasoning", "code", "instruction", "ui"):
        assert generate(dim, "20260704") == generate(dim, "20260704")
        assert generate(dim, "20260704") != generate(dim, "20260705") or dim == "ui"


def test_generators_use_no_assert_raise_or_while_true():
    for name in ("reasoning.py", "code.py", "instruction.py", "ui.py"):
        tree = ast.parse((ROOT / name).read_text())
        for node in ast.walk(tree):
            assert not isinstance(node, (ast.Assert, ast.Raise)), (name, node.lineno)
            if isinstance(node, ast.While):
                assert not (isinstance(node.test, ast.Constant) and node.test.value), (name, node.lineno)


def test_ui_prompts():
    prompts = []
    for seed in _daily("2026-01-01", 120):
        classic, variant = generate("ui", seed)
        assert classic.prompt.startswith("Draw a pelican riding a bicycle.")
        assert variant.prompt.startswith("Draw a penguin driving a tractor.")
        for q in (classic, variant):
            assert 'viewBox="0 0 400 300"' in q.prompt and "at least 8 shape elements" in q.prompt
        prompts.append(variant.prompt)
    assert len(set(prompts)) == 1

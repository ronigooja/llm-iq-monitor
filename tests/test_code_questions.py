import ast
import sys
import types
from dataclasses import dataclass
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parents[1] / "src"))

try:
    from llm_iq_monitor.questions.base import Question
except ModuleNotFoundError:
    @dataclass
    class Question:
        qid: str
        dim: str
        prompt: str
        kind: str
        expected: object
        meta: dict

    base = types.ModuleType("llm_iq_monitor.questions.base")
    base.Question = Question
    sys.modules[base.__name__] = base

from llm_iq_monitor.questions.code import extract_code, generate


def test_generation_is_deterministic_and_complete():
    first = generate("2026-11-02")
    second = generate("2026-11-02")
    assert len(first) == 12
    assert [q.meta for q in first] == [q.meta for q in second]
    assert all(q.kind == "code" and len(q.meta["tests"]) == 10 for q in first)


def test_generation_changes_with_seed():
    assert [q.meta for q in generate("a")] != [q.meta for q in generate("b")]


def test_extract_code_uses_last_valid_block():
    reply = """```python\ndef solve(x):\n    return 1\n```\n\n```text\ndef solve(x):\n    return 2\n```"""
    assert "return 2" in extract_code(reply)
    assert extract_code("no code") is None


def test_reference_solutions_pass_generated_cases():
    # Exercise the generated JSON-shaped cases with equivalent reference implementations.
    import itertools
    from collections import Counter

    refs = [
        lambda values, k: sum(v for i, v in enumerate(values) if i % abs(k) == 0) if k else 0,
        lambda values: max((sum(1 for _ in group) for _, group in itertools.groupby(values)), default=0),
        lambda values: sorted(set(values), reverse=True)[1] if len(set(values)) > 1 else None,
        lambda text: _balanced(text),
        lambda text: _rle(text),
        lambda left, right: Counter("".join(left.split()).casefold()) == Counter("".join(right.split()).casefold()),
        lambda value: _flatten(value),
        lambda numbers: sum(_prime(n) for n in numbers),
        lambda values, amount: values[-amount % len(values):] + values[:-amount % len(values)] if values else [],
        lambda intervals: _merge([sorted(x) for x in intervals]),
    ]
    for question, reference in zip(generate("test"), refs):
        for case in question.meta["tests"]:
            assert reference(*case["args"]) == case["expected"]


def _balanced(text):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack = []
    for char in text:
        if char in "([{": stack.append(char)
        elif char in pairs and (not stack or stack.pop() != pairs[char]): return False
    return not stack


def _rle(text):
    result = []
    for char in text:
        if result and result[-1][0] == char: result[-1][1] += 1
        else: result.append([char, 1])
    return result


def _flatten(value):
    return [item for value in value for item in (_flatten(value) if isinstance(value, list) else [value])]


def _prime(n):
    return n >= 2 and all(n % d for d in range(2, int(n ** .5) + 1))  # fine up to 10**6


def _merge(intervals):
    result = []
    for start, end in sorted(intervals):
        if result and start <= result[-1][1]: result[-1][1] = max(result[-1][1], end)
        else: result.append([start, end])
    return result

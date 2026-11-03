"""Basic public properties of the v4 code question generator."""

from llm_iq_monitor.questions.code import extract_code, generate


def test_generation_is_deterministic_and_complete():
    first = generate("2026-11-02")
    second = generate("2026-11-02")
    assert len(first) == 12
    assert first == second
    assert all(q.kind == "code" and len(q.meta["tests"]) == 10 for q in first)


def test_generation_changes_with_seed():
    assert [q.meta for q in generate("a")] != [q.meta for q in generate("b")]


def test_extract_code_uses_last_valid_block():
    reply = """```python\ndef solve(x):\n    return 1\n```\n\n```text\ndef solve(x):\n    return 2\n```"""
    assert "return 2" in extract_code(reply)
    assert extract_code("no code") is None

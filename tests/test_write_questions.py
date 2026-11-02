import re

import pytest

from llm_iq_monitor.questions import DIM_COUNTS, generate
from llm_iq_monitor.scoring import score


def _reference(question):
    rules = question.meta["rules"]
    brief = question.meta["brief"]
    points = next(r["items"] for r in rules if r["type"] == "required_selling_points")
    forbidden = next(r["items"] for r in rules if r["type"] == "forbidden_words")[0]
    ending = next((r.get("text") for r in rules if r["type"] == "closing_phrase"), None)
    if question.dim == "write_zh":
        text = "这是给目标用户准备的实用好选择，日常使用轻松方便，品质可靠。" + "。".join(points)
        length = next(r for r in rules if r["type"] == "zh_char_count")
        while len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text)) < length["min"]:
            text += "值得每天使用"
    else:
        text = (f"A thoughtful choice for {brief['audience']}, designed for everyday use with lasting comfort. "
                + " and ".join(points) + ". " + "Made to feel simple, useful, and dependable.")
        length = next(r for r in rules if r["type"] == "en_word_count")
        while len(re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])", text)) < length["min"]:
            text += " Better routines start with small choices."
    special = next((r for r in rules if r["type"] in ("bullet_count", "paragraph_count")), None)
    if special and special["type"] == "bullet_count":
        if question.dim == "write_zh":
            text = f"- {points[0]}，日常使用方便可靠\n- {points[1]}，为生活带来轻松"
            minimum = next(r["min"] for r in rules if r["type"] == "zh_char_count")
            while len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text)) < minimum:
                text += " 值得每天使用"
        else:
            text = f"- {points[0]}, made for easy everyday use\n- {points[1]}, made for easy everyday use"
            minimum = next(r["min"] for r in rules if r["type"] == "en_word_count")
            while len(re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])", text)) < minimum:
                text += " Better routines start with small choices."
    elif special and special["type"] == "paragraph_count":
        if question.dim == "write_zh":
            text = f"{points[0]}，{points[1]}，日常使用方便可靠。\n\n这是值得每天使用的安心选择。"
            minimum = next(r["min"] for r in rules if r["type"] == "zh_char_count")
            while len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text)) < minimum:
                text += " 值得每天使用"
        else:
            text = f"{points[0]} and {points[1]}, designed for easy everyday use.\n\nA dependable choice for better routines."
            minimum = next(r["min"] for r in rules if r["type"] == "en_word_count")
            while len(re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])", text)) < minimum:
                text += " Better routines start with small choices."
    if ending:
        text += ending
    return text.replace(forbidden, "not-this-word")


@pytest.mark.parametrize("dim", ["write_zh", "write_en"])
def test_writing_counts_and_determinism(dim):
    first = generate(dim, "2026-11-02")
    assert len(first) == 6 == DIM_COUNTS[dim]
    assert first == generate(dim, "2026-11-02")
    assert [q.qid for q in first] == [f"{dim}-{i:02d}" for i in range(1, 7)]
    assert all(q.kind == "rules" and isinstance(q.meta["brief"], dict) for q in first)


@pytest.mark.parametrize("dim", ["write_zh", "write_en"])
def test_reference_replies_pass(dim):
    for question in generate(dim, "reference"):
        assert score(question, _reference(question))


@pytest.mark.parametrize("dim", ["write_zh", "write_en"])
def test_each_writing_rule_can_fail(dim):
    for question in generate(dim, "mutations"):
        good = _reference(question)
        for rule in question.meta["rules"]:
            bad = good
            if rule["type"] in ("zh_char_count", "en_word_count"):
                bad = "x"
            elif rule["type"] == "required_selling_points":
                bad = good.replace(rule["items"][0], "missing")
            elif rule["type"] == "forbidden_words":
                bad = good + " " + rule["items"][0]
            elif rule["type"] == "bullet_count":
                bad = good + "\n- extra"
            elif rule["type"] == "paragraph_count":
                bad = good + "\n\nextra"
            elif rule["type"] == "closing_phrase":
                bad = good.removesuffix(rule["text"]) + "wrong"
            assert not score(question, bad), (question.qid, rule)


def test_chinese_count_ignores_formatting():
    question = generate("write_zh", "formatting")[0]
    rule = next(r for r in question.meta["rules"] if r["type"] == "zh_char_count")
    assert len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", "中文")) == 2
    assert score(question, _reference(question))
    assert not score(question, "中 文，。" * (rule["min"] // 2 - 1))

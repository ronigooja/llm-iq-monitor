import re

import pytest

from llm_iq_monitor.questions import DIM_COUNTS, generate
from llm_iq_monitor.scoring import score


def _reference(question):
    rules = question.meta["rules"]
    required = next(r["items"] for r in rules if r["type"] == "required_selling_points")
    forbidden = next(r["items"] for r in rules if r["type"] == "forbidden_words")[0]
    length = next(r for r in rules if r["type"] in ("zh_char_count", "en_word_count"))
    closing = next((r.get("text") for r in rules if r["type"] == "closing_phrase"), "")
    zh = question.dim == "write_zh"
    filler = "这是面向读者的清楚可靠实用说明，帮助大家理解背景并采取合适行动。" if zh else "This clear useful response gives readers practical context, a calm explanation, and a concrete next step."
    count = (lambda text: len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", text))) if zh else (lambda text: len(re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])", text)))
    text = ("、".join(required) + filler) if zh else (" and ".join(required) + ". " + filler)
    while count(text) < length["min"]:
        text += (" " if zh else " ") + filler
    while count(text) > length["max"]:
        text = text[:-1]
    if any(r["type"] == "bullet_count" for r in rules):
        text = "- " + text + "\n- " + filler
    elif any(r["type"] == "paragraph_count" and r["value"] == 2 for r in rules):
        split = len(text) // 2
        text = text[:split] + "\n\n" + text[split:]
    elif any(r["type"] == "paragraph_count" and r["value"] == 3 for r in rules) and not any(r["type"] == "numbered_count" for r in rules):
        split = len(text) // 3
        text = text[:split] + "\n\n" + text[split:2 * split] + "\n\n" + text[2 * split:]
    if any(r["type"] == "numbered_count" for r in rules):
        split = len(text) // 2
        text = "\n".join(f"{i}) {required[0]}" for i in range(1, 5)) + "\n\n" + text[:split] + "\n\n" + text[split:]
    if closing:
        text = text.rstrip() + "\n" + closing
    return text.replace(forbidden, "not-this-word")


@pytest.mark.parametrize("dim", ["write_zh", "write_en"])
def test_writing_counts_determinism_and_unique_prompts(dim):
    first = generate(dim, "2026-11-02")
    assert len(first) == 8 == DIM_COUNTS[dim]
    assert first == generate(dim, "2026-11-02")
    assert first != generate(dim, "2026-11-03")
    assert [q.qid for q in first] == [f"{dim}-{i:02d}" for i in range(1, 9)]
    assert len({q.prompt for q in first}) == 8


@pytest.mark.parametrize("dim", ["write_zh", "write_en"])
def test_reference_replies_pass(dim):
    for question in generate(dim, "reference"):
        assert score(question, _reference(question)), question.qid


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
            elif rule["type"] == "numbered_count":
                bad = good.replace("4) ", "5) ", 1)
            assert not score(question, bad), (question.qid, rule)


def test_chinese_count_ignores_formatting():
    question = generate("write_zh", "formatting")[0]
    rule = next(r for r in question.meta["rules"] if r["type"] == "zh_char_count")
    assert len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", "中文")) == 2
    assert score(question, _reference(question))
    assert not score(question, "中 文，。" * (rule["min"] // 2 - 1))


def test_english_article_is_correct_for_every_tone():
    for seed in ("article-1", "article-2", "article-3", "article-4"):
        for question in generate("write_en", seed):
            assert "a expert" not in question.prompt.lower()
            assert "an warm" not in question.prompt.lower()


def test_english_prompt_sentences_are_separated_and_chinese_meaning_is_retained():
    for seed in ("gap-1", "gap-2", "gap-3", "gap-4", "gap-5"):
        for question in generate("write_en", seed):
            prompt = question.prompt.replace("p.m.", "").replace("a.m.", "")
            assert not re.search(r"[.!?][A-Za-z]", prompt), question.qid
        for question in generate("write_zh", seed):
            required = next(rule["items"] for rule in question.meta["rules"] if rule["type"] == "required_selling_points")
            assert all(item in question.prompt for item in required), question.qid
            assert "中文汉字数必须在" in question.prompt

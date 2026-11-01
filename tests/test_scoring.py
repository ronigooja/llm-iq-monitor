from llm_iq_monitor.questions import generate
from llm_iq_monitor.scoring import extract_answer, score


def test_answer_protocol_uses_last_answer_line():
    assert extract_answer("ANSWER: wrong\nnotes\nANSWER: right") == "right"


def test_reference_answers_score_and_wrong_answers_fail():
    for dim in ("trap", "math", "logic", "science"):
        for question in generate(dim, "test"):
            assert score(question, f"ANSWER: {question.expected}")
            assert not score(question, "ANSWER: definitely-wrong")


def test_instruction_rules():
    question = generate("instruction", "test")[0]
    rules = question.meta["rules"]
    count = next(x["value"] for x in rules if x["type"] == "bullet_count")
    word = next(x["word"] for x in rules if x["type"] == "keyword_count")
    reply = "\n".join(f"- {word}" if i == 0 else "- calm" for i in range(count))
    assert score(question, reply)
    assert not score(question, reply.replace(word, "LOUD"))

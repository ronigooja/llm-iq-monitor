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
    from llm_iq_monitor.questions.base import Question

    rules = [{"type": "dash_bullets", "value": 2}, {"type": "keyword_exact", "word": "amber", "value": 1},
             {"type": "banned_words", "items": ["very"]}, {"type": "lowercase"}, {"type": "no_commas"}]
    question = Question("instruction-01", "instruction", "", "rules", None, {"rules": rules})
    reply = "- an amber light.\n- a calm room."
    assert score(question, reply)
    assert not score(question, reply.replace("amber", "LOUD"))
    assert not score(question, reply.replace("amber", "ambers"))
    assert not score(question, reply + "\n- very nice.")


def test_answer_line_accepts_markdown_and_latex():
    assert extract_answer("**ANSWER:** 42") == "42"
    assert extract_answer("**ANSWER: 3/7**") == "3/7"
    assert extract_answer("ANSWER: $\\boxed{12}$".replace("$", "")) == "12"

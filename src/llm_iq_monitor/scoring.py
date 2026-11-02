"""Machine scoring for non-code benchmark questions."""

import math
import re
from fractions import Fraction


def extract_answer(reply: str) -> str | None:
    matches = re.findall(r"^\s*ANSWER:\s*(.*?)\s*$", reply, flags=re.I | re.M)
    return matches[-1].strip() if matches else None


def _number(text: str) -> float:
    text = text.strip().replace(",", "")
    return float(re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?", text).group())


def _rules(question, reply):
    """Apply rule metadata; Chinese length counts Han characters, not formatting."""
    rules = question.meta.get("rules", [])
    lines = [x for x in reply.splitlines() if x.strip()]
    for rule in rules:
        typ = rule["type"]
        if typ == "bullet_count" and sum(bool(re.match(r"^\s*[-*•]\s+", x)) for x in lines) != rule["value"]: return False
        if typ == "paragraph_count" and len([p for p in re.split(r"\n\s*\n", reply.strip()) if p.strip()]) != rule["value"]: return False
        if typ == "zh_char_count":
            count = len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", reply))
            if not rule["min"] <= count <= rule["max"]: return False
        if typ == "en_word_count":
            count = len(re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])", reply))
            if not rule["min"] <= count <= rule["max"]: return False
        if typ == "required_selling_points" and any(item.casefold() not in reply.casefold() for item in rule["items"]): return False
        if typ == "forbidden_words" and any(re.search(re.escape(item), reply, re.I) for item in rule["items"]): return False
        if typ == "closing_phrase" and not reply.rstrip().endswith(rule["text"]): return False
        if typ == "lowercase" and reply != reply.lower(): return False
        if typ == "no_commas" and "," in reply: return False
        if typ == "keyword_count" and len(re.findall(rf"\b{re.escape(rule['word'])}\b", reply, re.I)) != rule["value"]: return False
        if typ == "forbidden" and re.search(rf"\b{re.escape(rule['word'])}\b", reply, re.I): return False
        if typ == "max_words" and len(reply.split()) > rule["value"]: return False
        if typ == "ending" and not reply.rstrip().endswith(rule["text"]): return False
    return True


def score(question, reply: str) -> bool:
    if question.kind == "code":
        raise NotImplementedError("code scoring is handled by the sandbox")
    if question.kind == "rules": return _rules(question, reply)
    answer = extract_answer(reply)
    if answer is None: return False
    expected = question.expected
    try:
        if question.kind == "exact":
            clean = lambda x: re.sub(r"[.,]$", "", x.strip().lower().replace(",", ""))
            return clean(answer) == clean(str(expected))
        if question.kind == "int": return int(_number(answer)) == int(expected) and _number(answer).is_integer()
        if question.kind == "fraction": return Fraction(answer.replace(" ", "")) == Fraction(expected)
        if question.kind == "num":
            got = _number(answer); exp = float(expected)
            return math.isclose(got, exp, rel_tol=.01, abs_tol=1e-12)
    except (ValueError, TypeError, ZeroDivisionError, AttributeError):
        return False
    raise ValueError(f"unknown scoring kind: {question.kind}")

"""Deterministic scoring for machine-checked benchmark questions."""
import json, math, re
from fractions import Fraction

def extract_answer(reply: str) -> str | None:
    matches = re.findall(r"^\s*ANSWER:\s*(.*?)\s*$", reply, flags=re.I | re.M)
    return matches[-1].strip() if matches else None

def _number(text: str) -> float:
    text = text.replace(",", "").replace("×", "x").replace("\\times", "x").replace("\\", "")
    text = re.sub(r"\\text\{[^}]*\}|\\times|\\\(|\\\)|\\\s", "", text)
    text = re.sub(r"\^\{([^}]*)\}", r"^\1", text)
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+|\s*x\s*10\^?[-+]?\d+)?", text, re.I)
    if not match: raise ValueError
    token = match.group().replace(" ", "")
    if re.search(r"x10", token, re.I):
        a, b = re.split(r"x10\^?", token, flags=re.I); return float(a) * 10 ** int(b)
    return float(token)

def _json_object(text):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try: return decoder.raw_decode(text[match.start():])[0]
        except json.JSONDecodeError: continue
    return None

def _rules(question, reply):
    rules = question.meta.get("rules", []); lines = [x for x in reply.splitlines() if x.strip()]
    for rule in rules:
        typ = rule["type"]
        if typ == "bullet_count" and sum(bool(re.match(r"^\s*[-*•]\s+", x)) for x in lines) != rule["value"]: return False
        if typ == "paragraph_count" and len([p for p in re.split(r"\n\s*\n", reply.strip()) if p.strip()]) != rule["value"]: return False
        if typ == "zh_char_count" and not rule["min"] <= len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", reply)) <= rule["max"]: return False
        if typ == "en_word_count" and not rule["min"] <= len(re.findall(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])", reply)) <= rule["max"]: return False
        if typ == "required_selling_points" and any(x.casefold() not in reply.casefold() for x in rule["items"]): return False
        if typ == "forbidden_words" and any(re.search(re.escape(x), reply, re.I) for x in rule["items"]): return False
        if typ in ("closing_phrase", "ending") and not reply.rstrip().endswith(rule["text"]): return False
        if typ == "lowercase" and reply != reply.lower(): return False
        if typ == "no_commas" and "," in reply: return False
        if typ == "keyword_count" and len(re.findall(rf"\b{re.escape(rule['word'])}\b", reply, re.I)) != rule["value"]: return False
        if typ == "forbidden" and re.search(rf"\b{re.escape(rule['word'])}\b", reply, re.I): return False
        if typ == "max_words" and len(reply.split()) > rule["value"]: return False
        if typ == "nested_string_max_words" and any(len(x.lstrip(" -*•").split()) > rule["value"] for x in lines): return False
    return True

def score(question, reply: str) -> bool:
    if question.kind in ("code", "svg"): raise NotImplementedError(f"{question.kind} scoring is handled externally")
    if question.kind == "rules": return _rules(question, reply)
    if question.kind == "json": return _json_object(reply) == question.expected
    answer = extract_answer(reply)
    if answer is None: return False
    expected = question.expected
    try:
        if question.kind == "unknown": return answer.strip().rstrip(".").casefold() == "unknown"
        if question.kind == "exact":
            clean = lambda x: re.sub(r"[.,]$", "", x.strip().lower().replace(",", ""))
            options = question.meta.get("options")
            if options:
                found = [x for x in options if re.search(rf"\b{re.escape(str(x))}\b", answer, re.I)]
                return len(found) == 1 and clean(found[0]) == clean(str(expected))
            return clean(answer) == clean(str(expected)) or bool(re.search(rf"\b{re.escape(str(expected))}\b", answer, re.I))
        if question.kind == "int": return int(_number(answer)) == int(expected) and _number(answer).is_integer()
        if question.kind == "fraction": return Fraction(answer.replace(" ", "")) == Fraction(expected)
        if question.kind == "num": return math.isclose(_number(answer), float(expected), rel_tol=.01, abs_tol=1e-12)
    except (ValueError, TypeError, ZeroDivisionError, AttributeError): return False
    raise ValueError(f"unknown scoring kind: {question.kind}")

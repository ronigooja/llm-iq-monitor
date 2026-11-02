"""Deterministic scoring for machine-checked benchmark questions."""
import json, math, re
from fractions import Fraction

_WORD = re.compile(r"(?<![A-Za-z])[A-Za-z]+(?:['-][A-Za-z]+)*(?![A-Za-z])")
_DECOR = "*_`\"'“”‘’ "


def extract_answer(reply: str) -> str | None:
    # Accept plain `ANSWER: x` plus common Markdown decorations such as
    # `**ANSWER:** x`, `**ANSWER: x**` or `> ANSWER: `x``.
    matches = re.findall(r"^[\s>#*_`]*ANSWER[*_`]*\s*:\s*(.*?)\s*$", reply, flags=re.I | re.M)
    if not matches:
        return None
    answer = matches[-1].strip().strip(_DECOR).strip()
    return re.sub(r"^\\boxed\{(.*)\}$", r"\1", answer).strip(_DECOR)


def _number(text: str) -> float:
    text = text.replace(",", "").replace("\u2212", "-").replace("×", "x").replace("\\times", "x").replace("\\", "")
    text = re.sub(r"\\text\{[^}]*\}|\\times|\\\(|\\\)|\\\s", "", text)
    text = re.sub(r"\^\{([^}]*)\}", r"^\1", text)
    match = re.search(r"[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+|\s*x\s*10\^?[-+]?\d+)?", text, re.I)
    if not match: raise ValueError
    token = match.group().replace(" ", "")
    if re.search(r"x10", token, re.I):
        a, b = re.split(r"x10\^?", token, flags=re.I); return float(a) * 10 ** int(b)
    return float(token)


def _fraction(text: str) -> Fraction:
    text = text.replace("\u2212", "-").replace("$", "")
    latex = re.search(r"(-?)\\d?frac\{\s*(-?\d+)\s*\}\{\s*(-?\d+)\s*\}", text)
    if latex:
        return Fraction(int(latex.group(2)), int(latex.group(3))) * (-1 if latex.group(1) else 1)
    plain = re.search(r"(-?\d+)\s*/\s*(-?\d+)", text)
    if plain:
        return Fraction(int(plain.group(1)), int(plain.group(2)))
    return Fraction(text.strip().rstrip("."))


def _json_object(text):
    decoder = json.JSONDecoder()
    for match in re.finditer(r"\{", text):
        try: return decoder.raw_decode(text[match.start():])[0]
        except json.JSONDecodeError: continue
    return None


def strict_equal(left, right) -> bool:
    """JSON equality that keeps booleans, numbers, strings and null apart."""
    if isinstance(left, bool) or isinstance(right, bool):
        return type(left) is type(right) and left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return left == right
    if isinstance(left, dict) and isinstance(right, dict):
        return left.keys() == right.keys() and all(strict_equal(left[k], right[k]) for k in left)
    if isinstance(left, list) and isinstance(right, list):
        return len(left) == len(right) and all(strict_equal(a, b) for a, b in zip(left, right))
    return type(left) is type(right) and left == right


def sentences(text: str) -> list[str]:
    """Split on runs of . ! ? and drop stretches that contain no word."""
    return [part for part in re.split(r"[.!?]+", text) if _WORD.search(part)]


def _json_reply(reply: str):
    text = reply.strip()
    fenced = re.fullmatch(r"```(?:json)?[ \t]*\n(.*?)\n?[ \t]*```", text, flags=re.S | re.I)
    try:
        return json.loads(fenced.group(1) if fenced else text)
    except (json.JSONDecodeError, ValueError):
        return None


def _rule_holds(rule, reply, lines) -> bool:
    typ = rule["type"]
    stripped = [x.lstrip() for x in lines]
    if typ == "bullet_count": return sum(bool(re.match(r"^\s*[-*•]\s+", x)) for x in lines) == rule["value"]
    if typ == "paragraph_count": return len([p for p in re.split(r"\n\s*\n", reply.strip()) if p.strip()]) == rule["value"]
    if typ == "zh_char_count": return rule["min"] <= len(re.findall(r"[\u3400-\u4dbf\u4e00-\u9fff]", reply)) <= rule["max"]
    if typ == "en_word_count": return rule["min"] <= len(_WORD.findall(reply)) <= rule["max"]
    if typ == "required_selling_points": return all(x.casefold() in reply.casefold() for x in rule["items"])
    if typ == "forbidden_words": return not any(re.search(re.escape(x), reply, re.I) for x in rule["items"])
    if typ in ("closing_phrase", "ending"): return reply.rstrip().endswith(rule["text"])
    if typ == "lowercase": return reply == reply.lower()
    if typ == "no_commas": return "," not in reply and "，" not in reply
    if typ == "keyword_count": return len(re.findall(rf"\b{re.escape(rule['word'])}\b", reply, re.I)) == rule["value"]
    if typ == "forbidden": return not re.search(rf"\b{re.escape(rule['word'])}\b", reply, re.I)
    if typ == "max_words": return len(reply.split()) <= rule["value"]
    if typ == "nested_string_max_words": return all(len(x.lstrip(" -*•").split()) <= rule["value"] for x in lines)
    # v2 instruction rules; "word" means a match of ``_WORD`` throughout.
    words = [w.casefold() for w in _WORD.findall(reply)]
    if typ == "keyword_exact": return words.count(rule["word"].casefold()) == rule["value"]
    if typ == "banned_words": return not {x.casefold() for x in rule["items"]} & set(words)
    if typ == "no_digits": return not re.search(r"\d", reply)
    if typ == "sentence_count": return len(sentences(reply)) == rule["value"]
    if typ == "min_words_per_sentence": return all(len(_WORD.findall(s)) >= rule["value"] for s in sentences(reply))
    if typ == "max_words_per_sentence": return all(len(_WORD.findall(s)) <= rule["value"] for s in sentences(reply))
    if typ == "opening_phrase": return reply.lstrip().startswith(rule["text"])
    if typ == "dash_bullets":
        marked = [x for x in stripped if x[:1] in ("-", "*", "•")]
        return len(marked) == rule["value"] and all(x.startswith("- ") for x in marked)
    if typ == "numbered_count":
        marked = [x for x in stripped if re.match(r"\d+[).]", x)]
        return (len(marked) == rule["value"]
                and all(x.startswith(f"{i}) ") for i, x in enumerate(marked, 1)))
    if typ == "acrostic":
        return (len(stripped) == len(rule["word"])
                and all(x[:1].casefold() == c.casefold() for x, c in zip(stripped, rule["word"])))
    if typ == "line_prefix":
        return len(stripped) == rule["value"] and all(x.startswith(rule["marker"]) for x in stripped)
    if typ == "json_keys":
        data = _json_reply(reply)
        return (isinstance(data, dict) and sorted(data) == sorted(rule["keys"])
                and all(isinstance(v, str) and rule["min_words"] <= len(_WORD.findall(v)) <= rule["max_words"]
                        for v in data.values()))
    return False


def _rules(question, reply):
    lines = [x for x in reply.splitlines() if x.strip()]
    return all(_rule_holds(rule, reply, lines) for rule in question.meta.get("rules", []))


def score(question, reply: str) -> bool:
    if question.kind in ("code", "svg"): raise NotImplementedError(f"{question.kind} scoring is handled externally")
    if question.kind == "rules": return _rules(question, reply)
    if question.kind == "json":
        data = _json_object(reply)
        return data is not None and strict_equal(data, question.expected)
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
        if question.kind == "fraction": return _fraction(answer) == Fraction(expected)
        if question.kind == "num": return math.isclose(_number(answer), float(expected), rel_tol=.01, abs_tol=1e-12)
    except (ValueError, TypeError, ZeroDivisionError, AttributeError): return False
    raise ValueError(f"unknown scoring kind: {question.kind}")

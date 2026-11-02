"""v2 instruction questions: satisfiable rule sets, failing mutations, independent extraction checks."""

import datetime as dt
import json
import re
from decimal import Decimal

import pytest

from llm_iq_monitor.questions import generate
from llm_iq_monitor.questions.instruction import _TEMPLATES, TEMPLATE_ORDER, count_words
from llm_iq_monitor.scoring import _rule_holds, score, sentences

SEEDS = [f"i{n}" for n in range(200)]
START = {"a": "always", "b": "bring", "c": "come", "d": "do", "e": "each", "g": "give", "h": "have", "i": "in",
         "l": "look", "m": "make", "n": "next", "o": "our", "p": "please", "r": "read", "s": "some", "t": "then",
         "u": "use", "y": "you"}
FILLER = ("with", "care", "and", "keep", "this", "note", "close", "at", "hand", "for", "all", "of", "us", "today")


@pytest.fixture(scope="module")
def questions():
    return {seed: generate("instruction", seed) for seed in SEEDS}


def _rules_qs(questions):
    return [q for qs in questions.values() for q in qs if q.kind == "rules"]


def _get(rules, kind):
    return next((r for r in rules if r["type"] == kind), None)


def _sentence(first, length, keywords=0, keyword=""):
    words = [first] + [keyword] * keywords
    filler = iter(FILLER * 10)
    while len(words) < length:
        words.append(next(filler))
    return " ".join(words) + "."


def _lengths(count, low, high, total, fixed):
    """Per-sentence word counts in [low, high] summing to ``total`` when possible."""
    base = max(low, min(high, 8)) if total is None else low
    sizes = [fixed.get(i, (base, high))[0] for i in range(count)]
    caps = [fixed.get(i, (low, high))[1] for i in range(count)]
    spare = (total or 0) - sum(sizes)
    for i in range(count):
        add = max(0, min(spare, caps[i] - sizes[i]))
        sizes[i] += add
        spare -= add
    return sizes


def reference_reply(question):
    rules = question.meta["rules"]
    structure = rules[0]
    keyword = _get(rules, "keyword_exact")
    kw, n_kw = keyword["word"], keyword["value"]
    if structure["type"] == "json_keys":
        values = {}
        for index, key in enumerate(structure["keys"]):
            uses = n_kw if index == 0 else 0
            values[key] = _sentence("please", max(structure["min_words"], uses + 1), uses, kw).rstrip(".")
        return json.dumps(values, indent=2)
    opening = _get(rules, "opening_phrase")
    closing = _get(rules, "closing_phrase")
    sc = _get(rules, "sentence_count")
    low = (_get(rules, "min_words_per_sentence") or {"value": 3})["value"]
    high = (_get(rules, "max_words_per_sentence") or {"value": 30})["value"]
    words = _get(rules, "en_word_count")
    kind = structure["type"]
    units = len(structure["word"]) if kind == "acrostic" else structure["value"]
    list_like = kind in ("dash_bullets", "numbered_count")
    total = sc["value"] if sc else units + (1 if list_like else 0) + (1 if closing else 0)
    fixed = {}
    if opening:
        fixed[0] = (max(low, count_words(opening["text"]) + 1), high)
    if closing:
        fixed[total - 1] = (count_words(closing["text"]),) * 2
    target = None
    if words:
        target = (words["min"] + words["max"]) // 2
    sizes = _lengths(total, max(low, 2), high, target, fixed)
    # Which sentences are list items / lines.
    if list_like:
        intro = total - units - (1 if closing else 0)
        assert intro >= (1 if opening else 0)
        item_idx = list(range(intro, intro + units))
    else:
        item_idx = list(range(total))
    free = [i for i in range(total) if not (closing and i == total - 1)]
    keyword_plan = {i: 0 for i in range(total)}
    remaining = n_kw
    for i in free:
        room = sizes[i] - 1 - (count_words(opening["text"]) if opening and i == 0 else 0)
        take = min(room, remaining)
        keyword_plan[i] = take
        remaining -= take
    assert remaining == 0
    texts = []
    for i in range(total):
        if closing and i == total - 1:
            texts.append(closing["text"])
            continue
        if opening and i == 0:
            head = opening["text"]
            body = _sentence("x", sizes[i] - count_words(head) + 1, keyword_plan[i], kw).split(" ", 1)[1]
            texts.append(f"{head} {body}")
            continue
        first = "please"
        texts.append(_sentence(first, sizes[i], keyword_plan[i], kw))
    if kind == "dash_bullets" or kind == "numbered_count":
        lines = []
        intro = item_idx[0]
        if intro:
            lines.append(" ".join(texts[:intro]))
        for number, i in enumerate(item_idx, 1):
            lines.append(("- " if kind == "dash_bullets" else f"{number}) ") + texts[i])
        if closing:
            lines.append(texts[-1])
        return "\n".join(lines)
    # Acrostic, line prefix and paragraphs: ``units`` lines/paragraphs, each with >= 1 sentence.
    groups = [[i] for i in range(units)]
    for i in range(units, total):
        groups[-1].append(i)
    if kind == "acrostic":
        word = structure["word"].lower()
        for g, letter in zip(groups, word):
            first = texts[g[0]].split(" ", 1)
            texts[g[0]] = START[letter] + " " + first[1]
        lines = [" ".join(texts[i] for i in g) for g in groups]
        return "\n".join(lines)
    if kind == "line_prefix":
        return "\n".join(structure["marker"] + " ".join(texts[i] for i in g) for g in groups)
    return "\n\n".join(" ".join(texts[i] for i in g) for g in groups)


def test_layout(questions):
    for qs in questions.values():
        assert [q.qid for q in qs] == [f"instruction-{i:02d}" for i in range(1, 15)]
        assert [q.kind for q in qs] == ["rules"] * 10 + ["json"] * 4
        assert len({q.meta["template"] for q in qs[:10]}) >= 6
        assert all(5 <= len(q.meta["rules"]) <= 7 for q in qs[:10])


def test_filler_is_neutral():
    banned = {w for t in _TEMPLATES.values() for w in t["banned"]}
    keywords = {w for t in _TEMPLATES.values() for w in t["keywords"]}
    assert not (set(FILLER) | set(START.values())) & (banned | keywords | {"x"})


def test_reference_reply_satisfies_every_rule(questions):
    for q in _rules_qs(questions):
        reply = reference_reply(q)
        lines = [x for x in reply.splitlines() if x.strip()]
        failed = [r for r in q.meta["rules"] if not _rule_holds(r, reply, lines)]
        assert not failed, (q.meta["rules"], reply)
        assert score(q, reply)


def _mutate(rule, reply):
    kind = rule["type"]
    first_stop = r"\.(?=\s*\S)"
    if kind == "dash_bullets":
        return reply + "\n- please keep this."
    if kind == "numbered_count":
        return reply.replace("2) ", "3) ", 1)
    if kind in ("acrostic", "line_prefix"):
        return reply + "\nzz please keep this."
    if kind == "paragraph_count":
        return reply + "\n\nplease keep this."
    if kind == "json_keys":
        data = json.loads(reply)
        data["extra"] = "please keep this note"
        return json.dumps(data)
    if kind == "keyword_exact":
        return re.sub(rf"\b{rule['word']}\b", "care", reply, count=1, flags=re.I)
    if kind == "banned_words":
        return reply + " " + rule["items"][0]
    if kind == "lowercase":
        return re.sub(r"[a-z]", lambda m: m.group().upper(), reply, count=1)
    if kind == "no_commas":
        return reply + ","
    if kind == "no_digits":
        return reply + " 7"
    if kind == "sentence_count":
        return re.sub(first_stop, " and", reply, count=1)
    if kind == "min_words_per_sentence":
        return re.sub(first_stop, ". ok.", reply, count=1)
    if kind == "max_words_per_sentence":
        return re.sub(first_stop, " " + "and " * 40 + ".", reply, count=1)
    if kind == "opening_phrase":
        return "so " + reply
    if kind == "closing_phrase":
        return reply.rstrip(".") + " now."
    if kind == "en_word_count":
        return reply + " and" * rule["max"]
    raise AssertionError(kind)


def test_each_rule_can_fail(questions):
    for q in _rules_qs(questions)[:400]:
        good = reference_reply(q)
        for rule in q.meta["rules"]:
            bad = _mutate(rule, good)
            lines = [x for x in bad.splitlines() if x.strip()]
            assert not _rule_holds(rule, bad, lines), (rule, bad)


def test_rules_vary_and_prompts_unique(questions):
    for name in TEMPLATE_ORDER:
        found = [q for q in _rules_qs(questions) if q.meta["template"] == name]
        assert len({q.prompt for q in found}) >= 20, name
        assert len({json.dumps(q.meta["rules"]) for q in found}) >= 20, name


def test_sentence_and_word_definitions():
    assert len(sentences("One two. Three?! Four...\n- five")) == 4
    assert len(sentences("1) . - ok")) == 1
    assert count_words("well-known don't 42 x-ray, e.g.") == 5


def test_scorer_rejects_typical_failures(questions):
    q = next(q for q in _rules_qs(questions) if q.meta["rules"][0]["type"] == "json_keys")
    good = reference_reply(q)
    assert score(q, "```json\n" + good + "\n```")
    assert not score(q, "Here is the JSON:\n" + good)


# --- extraction ---------------------------------------------------------------

def _parse_date(text, slash_order, year):
    for fmt in ("%d %B %Y",):
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            pass
    if "/" in text:
        return dt.datetime.strptime(text, "%d/%m/%y" if slash_order == "dmy" else "%m/%d/%y").date()
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", text):
        return dt.date.fromisoformat(text)
    cleaned = re.sub(r"(\d+)(st|nd|rd|th)$", r"\1", text)
    return dt.datetime.strptime(f"{cleaned} {year}", "%B %d %Y").date()


def _parse_money(text):
    value = Decimal(re.sub(r"[^\d.]", "", text))
    return int(value) if value == value.to_integral() else float(value)


def _json_qs(questions):
    return [q for qs in questions.values() for q in qs if q.kind == "json"]


def test_extraction_expected_from_surface_text(questions):
    for q in _json_qs(questions):
        text = q.prompt.split("Text:\n", 1)[1].split("\n\nReturn exactly", 1)[0]
        order = "dmy" if "day/month/year" in text else "mdy"
        year = int(re.search(r"without a year are in (\d{4})", text).group(1))
        styles = set()
        for key, value in q.expected.items():
            fmt, surface = q.meta["formats"][key], q.meta["surface"][key]
            assert f"\"{key}\"" in q.prompt
            if fmt == "missing":
                assert value is None
                continue
            if fmt != "bool":
                assert surface in text, (key, surface)
            if fmt in ("long", "slash", "ordinal", "iso"):
                styles.add(fmt)
                assert _parse_date(surface, order, year).isoformat() == value
                if fmt == "slash":
                    a, b = int(surface[:2]), int(surface[3:5])
                    assert a <= 12 and b <= 12 and a != b  # the stated order decides
            elif fmt == "money":
                assert _parse_money(surface) == value and type(_parse_money(surface)) is type(value)
            elif fmt == "int":
                assert int(re.sub(r"\D", "", surface)) == value
            elif fmt == "bool":
                assert isinstance(value, bool)
                continue
            else:
                assert surface == value
        assert {"long", "slash", "ordinal"} <= styles
        assert 10 <= len(q.expected) <= 12 and sum(v is None for v in q.expected.values()) == 1


def test_extraction_has_distractors(questions):
    for q in _json_qs(questions):
        text = q.prompt.split("Text:\n", 1)[1]
        money = re.findall(r"(?:€|\$|£|CHF )[\d,]+\.\d\d", text)
        expected_money = [v for k, v in q.expected.items() if q.meta["formats"][k] == "money"]
        assert len(money) > len(expected_money)  # at least one amount is a distractor
        person_keys = {"customer_name", "sales_rep", "guest_name", "booked_by", "technician", "attendee_name",
                       "registered_by"}
        names = [v for k, v in q.expected.items() if k in person_keys]
        firsts = [n.split()[0] for n in names]
        mentioned = set(re.findall(r"\b([A-Z][a-z]+ [A-Z][a-z]+)\b", text))
        assert len(names) == 2 and len(set(firsts)) == 1  # two people share a first name
        assert len({m for m in mentioned if m.split()[1] in {n.split()[1] for n in names}}) >= 3


def test_extraction_scoring_is_strict(questions):
    for q in _json_qs(questions)[:200]:
        good = json.dumps(q.expected)
        assert score(q, good)
        assert score(q, "```json\n" + json.dumps(q.expected, indent=2) + "\n```")
        missing = next(k for k, v in q.expected.items() if v is None)
        money = next(k for k, v in q.expected.items() if q.meta["formats"][k] == "money")
        slash = next(k for k, v in q.expected.items() if q.meta["formats"][k] == "slash")
        flag = next(k for k, v in q.expected.items() if isinstance(v, bool))
        day = dt.date.fromisoformat(q.expected[slash])
        mutations = [
            {**q.expected, missing: ""},
            {**q.expected, money: str(q.expected[money])},
            {**q.expected, slash: dt.date(day.year, day.day, day.month).isoformat()},
            {**q.expected, flag: int(q.expected[flag])},
            {k: v for k, v in q.expected.items() if k != missing},
        ]
        for bad in mutations:
            assert not score(q, json.dumps(bad)), bad

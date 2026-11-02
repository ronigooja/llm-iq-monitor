"""Independent re-derivation of every v2 reasoning answer.

Each check uses a different method from the generator: brute-force
enumeration for probabilities, day-by-day walks and Zeller's congruence for
calendars, regex parsing of the prompt text for tables and stories, and a
subprocess-free re-evaluation of Python expressions with full builtins.
"""

import datetime as dt
import itertools
import re
from collections import Counter
from fractions import Fraction

import pytest

from llm_iq_monitor.questions import generate
from llm_iq_monitor.questions.reasoning import TEMPLATES
from llm_iq_monitor.scoring import score

SEEDS = [f"s{n}" for n in range(200)]


@pytest.fixture(scope="module")
def questions():
    return {seed: generate("reasoning", seed) for seed in SEEDS}


def _by_template(questions, name):
    return [q for qs in questions.values() for q in qs if q.meta["template"] == name]


def _date(text):
    return dt.date.fromisoformat(text)


def _zeller_weekday(day):
    """Monday=0 via Zeller's congruence, independent of datetime.weekday()."""
    y, m, d = day.year, day.month, day.day
    if m < 3:
        m += 12
        y -= 1
    h = (d + 13 * (m + 1) // 5 + y % 100 + (y % 100) // 4 + (y // 100) // 4 + 5 * (y // 100)) % 7
    return (h + 5) % 7


def test_layout_and_counts(questions):
    assert len(TEMPLATES) == 18
    for qs in questions.values():
        assert [q.qid for q in qs] == [f"reasoning-{i:02d}" for i in range(1, 19)]
        assert sum(q.kind == "unknown" for q in qs) == 1
        assert len({q.prompt for q in qs}) == 18


def test_each_template_varies_and_is_non_trivial(questions):
    for name in set(TEMPLATES):
        found = _by_template(questions, name)
        prompts = {q.prompt for q in found[:40]}
        assert len(prompts) >= 20, name
        if name != "python_unknown":
            assert len({str(q.expected) for q in found}) >= 5, name


def test_ordering_unique_by_brute_force(questions):
    for q in _by_template(questions, "ordering")[:60]:
        facts = q.prompt.split("Facts: ", 1)[1].split(". Who is", 1)[0].split("; ")
        immediate, before = [], []
        for fact in facts:
            if " is immediately before " in fact:
                immediate.append(tuple(fact.split(" is immediately before ")))
            elif " is somewhere before " in fact:
                before.append(tuple(fact.split(" is somewhere before ")))
        names = q.meta["options"]
        position = int(re.search(r"position (\d+)", q.prompt).group(1))
        answers = set()
        for perm in itertools.permutations(names):
            pos = {n: i for i, n in enumerate(perm)}
            if all(pos[a] + 1 == pos[b] for a, b in immediate) and all(pos[a] < pos[b] for a, b in before):
                answers.add(perm[position - 1])
                if len(answers) > 1:
                    break
        assert answers == {q.expected}


def test_recurrence_closed_form(questions):
    for q in _by_template(questions, "recurrence"):
        a, b, n = q.meta["a"], q.meta["b"], q.meta["n"]
        # Two steps: x -> 3x + b - a.  Fixed point p = (a - b) / 2.
        pairs, odd = divmod(n - 1, 2)
        p = Fraction(a - b, 2)
        value = p + (a - p) * 3 ** pairs
        if odd:
            value = value * 3 + b
        assert value == q.expected


def test_friday13_by_daily_walk(questions):
    for q in _by_template(questions, "friday13"):
        start, end = _date(q.meta["start"]), _date(q.meta["end"])
        count, day = 0, start
        while day <= end:
            count += day.day == 13 and _zeller_weekday(day) == 4
            day += dt.timedelta(days=1)
        assert count == q.expected
        assert f"{start.isoformat()} is a {('Monday', 'Tuesday', 'Wednesday', 'Thursday', 'Friday', 'Saturday', 'Sunday')[_zeller_weekday(start)]}" in q.prompt


def test_business_days_from_prompt_text(questions):
    for q in _by_template(questions, "business_days"):
        start = _date(re.match(r"(\d{4}-\d{2}-\d{2})", q.prompt).group(1))
        holidays = {_date(x) for x in re.search(r"holidays: ([\d\-, ]+)\.", q.prompt).group(1).split(", ")}
        n = int(re.search(r"Business day (\d+) falls", q.prompt).group(1))
        ordinals = [o for o in range(start.toordinal() + 1, start.toordinal() + 120)
                    if _zeller_weekday(dt.date.fromordinal(o)) < 5 and dt.date.fromordinal(o) not in holidays]
        assert ordinals[n - 1] - start.toordinal() == q.expected
        # The distractor holidays must matter: without them the answer differs.
        plain = [o for o in range(start.toordinal() + 1, start.toordinal() + 120)
                 if _zeller_weekday(dt.date.fromordinal(o)) < 5]
        assert plain[n - 1] - start.toordinal() != q.expected


def test_transfer_probability_by_enumeration(questions):
    for q in _by_template(questions, "transfer_probability"):
        ra, ba, rb, bb = q.meta["urns"]
        k, colour, j = q.meta["k"], q.meta["colour"], q.meta["j"]
        urn_a = ["red"] * ra + ["blue"] * ba
        hit = total = 0
        for moved in itertools.combinations(range(len(urn_a)), k):
            reds = sum(urn_a[i] == "red" for i in moved)
            urn_b = ["red"] * (rb + reds) + ["blue"] * (bb + k - reds)
            for token in urn_b:
                if token == colour:
                    total += 1
                    hit += reds == j
        assert Fraction(hit, total) == q.expected
        assert 0 < q.expected < 1


def test_two_colour_probability_by_enumeration(questions):
    for q in _by_template(questions, "two_colour_probability"):
        bag = [c for c, n in zip("rbgy", q.meta["counts"]) for _ in range(n)]
        draws = list(itertools.combinations(range(len(bag)), q.meta["draws"]))
        good = sum(len({bag[i] for i in d}) == 2 for d in draws)
        assert Fraction(good, len(draws)) == q.expected


def test_room_story_replayed_from_text(questions):
    for q in _by_template(questions, "trap_room"):
        count = int(re.search(r"has (\d+) people in it", q.prompt).group(1))
        story = q.prompt.split("In order: ", 1)[1].split(". How many", 1)[0]
        for step in story.split("; then "):
            k = int(re.match(r"(?:all but )?(\d+)", step).group(1))
            if step.startswith("all but"):
                count = k
            elif step.endswith("walk in"):
                count += k
            elif step.endswith("leave the room"):
                count -= k
            assert count >= 0
        assert count == q.expected


def test_price_puzzle_by_search(questions):
    for q in _by_template(questions, "trap_price")[:60]:
        total, a, b = q.meta["total"], q.meta["a"], q.meta["b"]
        # big = mid + small + a, mid = small + b; scan every small price.
        found = [s for s in range(total + 1) if (s + b + s + a) + (s + b) + s == total]
        assert found == [q.expected]
        dollars = re.findall(r"\$([\d,]+\.\d\d)", q.prompt)
        assert round(float(dollars[0].replace(",", "")) * 100) == total


def test_shelter_story_by_simulation(questions):
    for q in _by_template(questions, "trap_all_but"):
        cats, dogs, k, m, l, p, j, qq, rr = q.meta["params"]
        shelter = {"cats": cats, "dogs": dogs}
        foster = 0
        shelter["cats"] = k
        shelter["cats"] += m
        shelter["dogs"] = l
        shelter["dogs"] += p
        foster += shelter["cats"] - j
        shelter["cats"] = j
        assert qq <= foster
        shelter["cats"] += qq
        shelter["dogs"] -= rr
        assert min(shelter.values()) >= 0
        target = q.meta["target"]
        value = sum(shelter.values()) if target == "animals" else shelter[target]
        assert value == q.expected


def test_letter_count_from_text(questions):
    for q in _by_template(questions, "trap_letters"):
        letter = re.search(r"letter '(.)'", q.prompt).group(1)
        text = re.search(r'text "([^"]+)"', q.prompt).group(1)
        assert Counter(text.casefold())[letter.casefold()] == q.expected
        assert q.expected >= 2


def _table(prompt):
    rows = []
    for line in prompt.splitlines():
        parts = [p.strip() for p in line.split("|")]
        if len(parts) == 5 and parts[0].startswith("R"):
            rows.append((parts[0], parts[1], int(parts[2]), int(parts[3]), int(parts[4])))
    return rows


def test_tables_by_independent_parsing(questions):
    for q in _by_template(questions, "table_group_second"):
        rows = _table(q.prompt)
        assert 10 <= len(rows) <= 14
        totals = Counter()
        for _, region, sales, returns, _ in rows:
            totals[region] += sales - returns
        ranked = totals.most_common()
        assert ranked[1][1] == q.expected and ranked[0][1] != ranked[1][1] != ranked[2][1]
    for q in _by_template(questions, "table_filter_range"):
        rows = _table(q.prompt)
        rating = int(re.search(r"rating is at least (\d+)", q.prompt).group(1))
        returns = int(re.search(r"strictly less than (\d+)", q.prompt).group(1))
        kept = sorted(r[2] for r in rows if r[4] >= rating and r[3] < returns)
        assert len(kept) >= 2 and kept[-1] - kept[0] == q.expected > 0
    for q in _by_template(questions, "table_ratio_kth"):
        rows = _table(q.prompt)
        k = int(re.search(r"What is the (\d)", q.prompt).group(1))
        rates = [int(Fraction(r[3] * 100, r[2])) for r in rows]
        assert sorted(rates)[-k] == q.expected
    for q in _by_template(questions, "table_above_group_mean"):
        rows = _table(q.prompt)
        strong = 0
        for row in rows:
            peers = [r[2] for r in rows if r[1] == row[1]]
            strong += Fraction(row[2]) > Fraction(sum(peers), len(peers))
        assert strong == q.expected >= 2


def test_python_answers_by_real_evaluation(questions):
    import math
    import string

    for name in ("python_division", "python_strings", "python_bytes_round", "python_unknown"):
        for q in _by_template(questions, name):
            expr = re.search(r"expression `(.+)` evaluate", q.prompt).group(1)
            try:
                value = eval(expr, {"math": math, "string": string})  # noqa: S307 - generated test input
            except AttributeError:
                value = "unknown"
            assert value == q.expected, expr


def test_reference_answers_score_in_common_formats(questions):
    for qs in list(questions.values())[:50]:
        for q in qs:
            expected = q.expected
            if q.kind == "fraction":
                variants = [f"{expected.numerator}/{expected.denominator}",
                            f"**ANSWER:** {expected.numerator} / {expected.denominator}",
                            f"\\frac{{{expected.numerator}}}{{{expected.denominator}}}"]
                wrong = f"{expected.numerator + 1}/{expected.denominator}"
            elif q.kind == "int":
                variants = [str(expected), f"**{expected}**", f"{expected:,}"]
                wrong = str(expected + 1)
            elif q.kind == "unknown":
                variants = ["unknown", "Unknown.", "`unknown`"]
                wrong = "42"
            else:
                variants = [str(expected), f"**{expected}**", f"{expected}."]
                wrong = next(x for x in q.meta["options"] if x != expected)
            for text in variants:
                reply = text if text.startswith("**ANSWER") else f"Work.\nANSWER: {text}"
                assert score(q, reply), (q.qid, reply)
            assert not score(q, f"ANSWER: {wrong}"), (q.qid, wrong)

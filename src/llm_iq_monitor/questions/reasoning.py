"""Deterministic reasoning questions (dataset v2).

The slot layout is fixed per dataset version (``TEMPLATES``).  Every expected
answer is computed here; tests re-derive each one with an independent method.
"""

import datetime as dt
import math
import string
from fractions import Fraction

from .base import Question, answer_prompt, rng_for

TEMPLATES = (
    "ordering", "recurrence", "friday13", "business_days", "transfer_probability", "two_colour_probability",
    "trap_room", "trap_price", "trap_all_but", "trap_letters",
    "table_group_second", "table_filter_range", "table_ratio_kth", "table_above_group_mean",
    "python_division", "python_strings", "python_unknown", "python_bytes_round",
)

WEEKDAYS = ("Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday")


def _ordering(r):
    names = r.sample(["Ada", "Bao", "Cleo", "Dara", "Eli", "Faye", "Gus", "Hana", "Ivan"], r.randint(7, 9))
    order = names[:]
    r.shuffle(order)
    # Adjacent links form a total chain, so the order is unique; the mix of
    # "immediately" and "somewhere" wording and two irrelevant facts are
    # reading distractors only.
    immediate_positions = set(r.sample(range(len(order) - 1), max(2, len(order) // 3)))
    before = [(order[i], order[i + 1]) for i in range(len(order) - 1)]
    facts = [
        f"{a} is immediately before {b}" if i in immediate_positions else f"{a} is somewhere before {b}"
        for i, (a, b) in enumerate(before)
    ]
    distractor_names = [name for name in names if name not in {order[0], order[-1]}]
    facts.extend([f"{distractor_names[0]} prefers tea", f"{distractor_names[-1]} wears blue"])
    r.shuffle(facts)
    target = r.choice(names)
    prompt = answer_prompt("Arrange these people from first to last. Facts: " + "; ".join(facts)
                           + f". Who is in position {order.index(target) + 1}?")
    return prompt, "exact", target, {"options": names, "unique": True, "order": order,
                                     "immediate_positions": sorted(immediate_positions)}


def _recurrence(r):
    a, b, n = r.randint(20, 90), r.randint(11, 35), r.randint(10, 14)
    value = a
    for k in range(1, n):
        value = value * 3 + b if k % 2 else value - a
    text = (f"A sequence starts at {a} (term 1). Each next term is made by applying one operation to the previous "
            f"term, alternating between two operations: first multiply by 3 and then add {b}; next subtract {a}. "
            f"So term 2 uses multiply-and-add, term 3 uses subtract, term 4 uses multiply-and-add, and so on. "
            f"What is term {n}?")
    return answer_prompt(text), "int", value, {"a": a, "b": b, "n": n}


def _random_date(r):
    first, last = dt.date(2024, 1, 1).toordinal(), dt.date(2034, 12, 31).toordinal()
    if r.random() < 0.3:
        # Late February of a leap year, so the leap day lies inside the range.
        return dt.date(r.choice([2024, 2028, 2032]), 2, r.randint(10, 27))
    return dt.date.fromordinal(r.randint(first, last))


def _friday13(r):
    start = _random_date(r)
    end = start + dt.timedelta(days=r.randint(430, 760))
    fridays = []
    year, month = start.year, start.month
    for _ in range(40):
        day = dt.date(year, month, 13)
        if day > end:
            break
        if day >= start and day.weekday() == 4:
            fridays.append(day)
        year, month = (year + 1, 1) if month == 12 else (year, month + 1)
    mode = r.randrange(3)
    if mode == 1 and fridays:
        end = fridays[-1]  # inclusive end date that is itself a Friday the 13th
    elif mode == 2 and fridays:
        start = fridays[0]  # inclusive start date that is itself a Friday the 13th
    count = sum(1 for day in fridays if start <= day <= end)
    text = (f"{start.isoformat()} is a {WEEKDAYS[start.weekday()]}. Using the Gregorian calendar (leap years included), "
            f"how many dates from {start.isoformat()} to {end.isoformat()}, both dates included, are a Friday that is "
            "also the 13th day of its month? Answer with an integer.")
    return answer_prompt(text), "int", count, {"start": start.isoformat(), "end": end.isoformat()}


def _advance_business_days(start, n, holidays):
    day, counted = start, 0
    for _ in range(400):
        day += dt.timedelta(days=1)
        if day.weekday() < 5 and day not in holidays:
            counted += 1
            if counted == n:
                break
    return day


def _business_days(r):
    start = _random_date(r)
    n = r.randint(18, 32)
    plain = _advance_business_days(start, n, set())
    window = [start + dt.timedelta(days=k) for k in range(1, (plain - start).days + 1)]
    weekdays = [d for d in window if d.weekday() < 5]
    weekends = [d for d in window if d.weekday() >= 5]
    holidays = set(r.sample(weekdays[:-1], r.randint(2, 3))) | {r.choice(weekends)}
    if r.random() < 0.5:
        holidays.add(start)  # counting starts after the start date: no effect
    result = _advance_business_days(start, n, holidays)
    holidays.add(result + dt.timedelta(days=r.randint(1, 9)))  # after the answer: no effect
    shown = sorted(holidays)
    r.shuffle(shown)
    text = (f"{start.isoformat()} is a {WEEKDAYS[start.weekday()]}. Business days are Monday to Friday, except these "
            f"public holidays: {', '.join(d.isoformat() for d in shown)}. A holiday that falls on a weekend is not "
            f"moved to another day. Counting starts after {start.isoformat()}: the first business day after it is "
            f"business day 1. Business day {n} falls how many calendar days after {start.isoformat()}? (If it were "
            f"the next day, the answer would be 1.) Answer with an integer.")
    expected = (result - start).days
    return answer_prompt(text), "int", expected, {"start": start.isoformat(), "n": n, "date": result.isoformat(),
                                                  "holidays": sorted(d.isoformat() for d in holidays)}


def _transfer_probability(r):
    ra, ba, rb, bb, k, colour, j = 4, 4, 3, 3, 2, "red", 1
    answer = Fraction(1, 2)
    for _ in range(50):
        ra, ba = r.randint(3, 7), r.randint(3, 7)
        rb, bb = r.randint(2, 6), r.randint(2, 6)
        k = r.choice([2, 3])
        colour = r.choice(["red", "blue"])
        j = r.randint(0, k)
        prior = [Fraction(math.comb(ra, x) * math.comb(ba, k - x), math.comb(ra + ba, k)) for x in range(k + 1)]
        like = [Fraction(rb + x if colour == "red" else bb + k - x, rb + bb + k) for x in range(k + 1)]
        answer = prior[j] * like[j] / sum(p * q for p, q in zip(prior, like))
        if 0 < answer < 1:
            break
    text = (f"Urn A holds {ra} red and {ba} blue tokens. Urn B holds {rb} red and {bb} blue tokens. {k} tokens are "
            f"drawn from urn A uniformly at random without replacement and all of them are put into urn B. Then one "
            f"token is drawn from urn B uniformly at random. Given that this token is {colour}, what is the "
            f"probability that exactly {j} of the {k} moved tokens are red? Give a reduced fraction a/b.")
    return answer_prompt(text), "fraction", answer, {"urns": [ra, ba, rb, bb], "k": k, "colour": colour, "j": j}


_COLOURS = ("red", "blue", "green", "yellow")


def _two_colour_probability(r):
    counts = [r.randint(2, 6) for _ in _COLOURS]
    draws = r.choice([3, 4])
    total = sum(counts)
    favourable = 0
    for a in range(4):
        for b in range(a + 1, 4):
            for x in range(1, draws):
                favourable += math.comb(counts[a], x) * math.comb(counts[b], draws - x)
    answer = Fraction(favourable, math.comb(total, draws))
    listing = ", ".join(f"{c} {name}" for c, name in zip(counts, _COLOURS))
    text = (f"A bag holds {listing} tokens; tokens differ only in colour. {draws} tokens are drawn at the same time, "
            f"uniformly at random. What is the probability that the drawn tokens show exactly two different colours "
            "(not one, not three or more)? Give a reduced fraction a/b.")
    return answer_prompt(text), "fraction", answer, {"counts": counts, "draws": draws}


_ROOM_PHRASES = {
    "enter": "{k} people walk in",
    "leave": "{k} people leave the room",
    "peek": "{k} people look in through the open door but stay in the corridor",
    "video": "{k} more colleagues join the meeting by video call from their homes",
    "return": "{k} people step out to take a phone call and all of them come back a minute later",
    "swap": "{k} people leave and the same number of different people enter in their place",
    "all_but": "all but {k} of the people currently in the room leave",
}


def _trap_room(r):
    initial = r.randint(5, 12)
    count = initial
    events = []
    steps = r.randint(8, 10)
    all_but_at = r.randint(2, steps - 3)
    for step in range(steps):
        if step == all_but_at and count > 2:
            keep = r.randint(1, count - 1)
            events.append(("all_but", keep))
            count = keep
            continue
        if count >= 2:
            kind = r.choice(["enter", "leave", r.choice(["peek", "video", "return", "swap"])])
        else:
            kind = r.choice(["enter", r.choice(["peek", "video"])])
        k = r.randint(1, count - 1) if kind in ("leave", "return", "swap") else r.randint(2, 6)
        if kind == "enter":
            count += k
        elif kind == "leave":
            count -= k
        events.append((kind, k))
    story = "; then ".join(_ROOM_PHRASES[kind].format(k=k) for kind, k in events)
    text = (f"A meeting room has {initial} people in it. Nobody else enters or leaves except as described. In order: "
            f"{story}. How many people are physically in the room at the end?")
    return answer_prompt(text), "int", count, {"initial": initial, "events": [list(e) for e in events]}


_ITEM_SETS = (("jacket", "hat", "scarf"), ("laptop", "bag", "mouse"), ("bicycle", "helmet", "lock"),
              ("guitar", "case", "strap"), ("camera", "lens", "tripod"), ("desk", "chair", "lamp"))


def _dollars(cents):
    return f"${cents // 100:,}.{cents % 100:02d}"


def _trap_price(r):
    big, mid, small = r.choice(_ITEM_SETS)
    s, b, a = r.randint(150, 2500), r.randint(100, 3000), r.randint(500, 9000)
    mid_price = s + b
    big_price = mid_price + s + a
    total = big_price + mid_price + s
    text = (f"A {big}, a {mid} and a {small} cost {_dollars(total)} in total. The {big} costs {_dollars(a)} more "
            f"than the {mid} and the {small} together. The {mid} costs {_dollars(b)} more than the {small}. What "
            f"does the {small} cost? Answer with an integer number of cents.")
    return answer_prompt(text), "int", s, {"total": total, "a": a, "b": b}


def _trap_all_but(r):
    cats, dogs = r.randint(9, 25), r.randint(6, 18)
    k, m = r.randint(2, cats - 2), r.randint(2, 9)
    l, p = r.randint(1, dogs - 2), r.randint(2, 8)
    j = r.randint(1, k + m - 1)
    q = r.randint(1, k + m - j)
    rr = r.randint(1, l + p - 1)
    final_cats, final_dogs = j + q, l + p - rr
    target = r.choice(["cats", "dogs", "animals"])
    expected = {"cats": final_cats, "dogs": final_dogs, "animals": final_cats + final_dogs}[target]
    text = (f"An animal shelter has {cats} cats and {dogs} dogs on Sunday evening. On Monday, all but {k} of the cats "
            f"are adopted. On Tuesday, {m} new cats arrive and all but {l} of the dogs are adopted. On Wednesday, {p} "
            f"new dogs arrive and all but {j} of the cats at the shelter are moved to foster homes. On Thursday, {q} "
            f"of the cats that were moved to foster homes on Wednesday come back to the shelter and {rr} dogs are "
            f"adopted. No other animals arrive or leave. How many {target} are at the shelter on Thursday evening?")
    return answer_prompt(text), "int", expected, {"target": target, "params": [cats, dogs, k, m, l, p, j, q, rr]}


_LONG_WORDS = ("Mississippi", "Assessment", "Bookkeeper", "Committee", "Parallelogram", "Abracadabra",
               "Onomatopoeia", "Unnecessarily", "Hippopotamus", "Strawberry", "Tennessee", "Possession",
               "Successfully", "Embarrassment", "Accommodation", "Mellifluous", "Referee", "Bubblegum",
               "Peppermint", "Kaleidoscope")


def _trap_letters(r):
    words = r.sample(_LONG_WORDS, 3)
    styled = [w.upper() if r.random() < 0.4 else w for w in words]
    phrase = " ".join(styled)
    lowered = phrase.lower()
    candidates = sorted(ch for ch in set(lowered) if ch.isalpha() and lowered.count(ch) >= 3)
    letter = r.choice(candidates or sorted(ch for ch in set(lowered) if ch.isalpha()))
    expected = lowered.count(letter)
    shown = letter.upper() if r.random() < 0.5 else letter
    text = (f"How many times does the letter {shown!r} appear in the text \"{phrase}\"? Uppercase and lowercase forms "
            "of the letter both count. Answer with an integer.")
    return answer_prompt(text), "int", expected, {"text": phrase, "letter": letter}


_REGIONS = ("North", "South", "East", "West")


def _table_rows(r, n):
    rows = []
    for idx, value in enumerate(r.sample(range(120, 980), n)):
        rows.append((f"R{idx + 1}", r.choice(_REGIONS), value, r.randint(max(1, value // 20), value // 3), r.randint(1, 9)))
    return rows


def _render_table(rows):
    return "\n".join(["id | region | sales | returns | rating"] + [" | ".join(map(str, row)) for row in rows])


def _net_totals(rows):
    totals = {}
    for row in rows:
        totals[row[1]] = totals.get(row[1], 0) + row[2] - row[3]
    return totals


def _table_group_second(r):
    rows = _table_rows(r, 12)
    for _ in range(50):
        rows = _table_rows(r, r.randint(10, 14))
        totals = _net_totals(rows)
        if len(totals) >= 3 and len(set(totals.values())) == len(totals):
            break
    totals = _net_totals(rows)
    expected = sorted(totals.values(), reverse=True)[1]
    text = (f"Read this table:\n{_render_table(rows)}\nFor each region, compute its net sales: the sum over its rows "
            "of (sales minus returns). Find the region with the second-largest net sales and answer with that "
            "region's net sales as an integer.")
    return answer_prompt(text), "int", expected, {"rows": [list(x) for x in rows]}


def _table_filter_range(r):
    rows, rating_t, returns_t = [], 1, 10 ** 6
    for _ in range(50):
        rows = _table_rows(r, r.randint(10, 14))
        rating_t = r.choice([row[4] for row in rows])
        returns_t = r.choice([row[3] for row in rows])
        kept = [row for row in rows if row[4] >= rating_t and row[3] < returns_t]
        if 3 <= len(kept) <= len(rows) - 3:
            break
    kept = [row for row in rows if row[4] >= rating_t and row[3] < returns_t]
    if len(kept) < 2:
        rating_t, returns_t, kept = 1, max(row[3] for row in rows) + 1, rows
    expected = max(row[2] for row in kept) - min(row[2] for row in kept)
    text = (f"Read this table:\n{_render_table(rows)}\nKeep only the rows whose rating is at least {rating_t} and "
            f"whose returns are strictly less than {returns_t}. Among the kept rows, what is the largest sales value "
            "minus the smallest sales value? Answer with an integer.")
    return answer_prompt(text), "int", expected, {"rows": [list(x) for x in rows], "rating_t": rating_t,
                                                  "returns_t": returns_t}


def _table_ratio_kth(r):
    rows = _table_rows(r, r.randint(10, 14))
    k = r.randint(2, 4)
    expected = sorted((row[3] * 100 // row[2] for row in rows), reverse=True)[k - 1]
    nth = {2: "2nd", 3: "3rd", 4: "4th"}[k]
    text = (f"Read this table:\n{_render_table(rows)}\nFor every row compute its return rate: returns divided by "
            "sales, times 100, rounded down to an integer (for example 37 returns on 180 sales gives 20). Sort all "
            f"rows' return rates from largest to smallest, keeping equal rates as separate entries (in the list 9, 7, "
            f"7, 5 the 2nd and 3rd largest are both 7). What is the {nth}-largest return rate? Answer with an integer.")
    return answer_prompt(text), "int", expected, {"rows": [list(x) for x in rows], "k": k}


def _strong_count(rows):
    groups = {}
    for row in rows:
        groups.setdefault(row[1], []).append(row[2])
    return sum(1 for row in rows if row[2] * len(groups[row[1]]) > sum(groups[row[1]]))


def _table_above_group_mean(r):
    rows = _table_rows(r, 12)
    for _ in range(50):
        rows = _table_rows(r, r.randint(10, 14))
        if _strong_count(rows) >= 2:
            break
    text = (f"Read this table:\n{_render_table(rows)}\nCall a row 'strong' when its sales are strictly greater than "
            "the average (arithmetic mean) sales of all rows in the same region, the row itself included. How many "
            "rows are strong? Answer with an integer.")
    return answer_prompt(text), "int", _strong_count(rows), {"rows": [list(x) for x in rows]}


# Not-making-things-up: questions about Python expressions.  Real ones are
# evaluated with the interpreter at generation time; the invented one calls a
# function name built from a seeded vocabulary that the module does not have.
_PY_MODULES = {"math": math, "string": string}
_PY_INTRO = ("In Python 3 (CPython 3.11 or later), after `import math, string` has run, what does the expression "
             "`{expr}` evaluate to? If evaluating it would raise an exception (for example because a name it uses "
             "does not exist), answer unknown. Otherwise answer with the resulting integer.")


def _evaluate(expr):
    safe = {"round": round, "len": len, "int": int, "divmod": divmod}
    return eval(expr, {"__builtins__": safe}, dict(_PY_MODULES))  # noqa: S307 - expression built by this module


def _python_division(r):
    b = r.randint(3, 9)
    a = r.choice([x for x in range(13, 200) if x % b])
    expr = f"(-{a}) // {b} + 10 * ((-{a}) % {b}) + int(-{a} / {b})"
    return answer_prompt(_PY_INTRO.format(expr=expr)), "int", _evaluate(expr), {"expr": expr}


def _python_strings(r):
    fields = [r.choice(["ab", "x", "", "id", "q", ""]) for _ in range(r.randint(4, 7))]
    if all(fields):
        fields[r.randrange(len(fields))] = ""
    unit = r.choice(["aba", "ana", "ses", "ere"])
    haystack = unit[:2] * r.randint(3, 7) + unit[0] + r.choice(["", "x", unit[1]])
    expr = f"len({','.join(fields)!r}.split(',')) * 10 + {haystack!r}.count({unit!r})"
    return answer_prompt(_PY_INTRO.format(expr=expr)), "int", _evaluate(expr), {"expr": expr}


_ACCENTED = ("café", "naïve", "über", "señor", "jalapeño", "crème", "façade", "smörgås", "piñata", "déjà", "résumé", "coöp")


def _python_bytes_round(r):
    word = r.choice(_ACCENTED)
    halves = [f"round({2 * r.randint(0, 60)}.5)", f"round({2 * r.randint(0, 60) + 1}.5)"]
    r.shuffle(halves)
    expr = f"len({word!r}.encode('utf-8')) + {halves[0]} + {halves[1]}"
    return answer_prompt(_PY_INTRO.format(expr=expr)), "int", _evaluate(expr), {"expr": expr}


_FAKE_PREFIX = ("fold", "weave", "spread", "pivot", "mirror", "splice", "braid", "ripple", "nest", "scatter")
_FAKE_SUFFIX = ("digits", "pairs", "runs", "bits", "span", "halves", "steps", "blocks")


def _python_unknown(r):
    module = r.choice(sorted(_PY_MODULES))
    name = "never_defined_zz"
    for _ in range(20):
        candidate = f"{r.choice(_FAKE_PREFIX)}_{r.choice(_FAKE_SUFFIX)}"
        if not hasattr(_PY_MODULES[module], candidate):
            name = candidate
            break
    arg = r.randint(100, 9999)
    expr = f"round({r.randint(0, 120)}.5) + {module}.{name}({arg})"
    return answer_prompt(_PY_INTRO.format(expr=expr)), "unknown", "unknown", {"expr": expr, "module": module, "name": name}


_BUILDERS = {
    "ordering": _ordering,
    "recurrence": _recurrence,
    "friday13": _friday13,
    "business_days": _business_days,
    "transfer_probability": _transfer_probability,
    "two_colour_probability": _two_colour_probability,
    "trap_room": _trap_room,
    "trap_price": _trap_price,
    "trap_all_but": _trap_all_but,
    "trap_letters": _trap_letters,
    "table_group_second": _table_group_second,
    "table_filter_range": _table_filter_range,
    "table_ratio_kth": _table_ratio_kth,
    "table_above_group_mean": _table_above_group_mean,
    "python_division": _python_division,
    "python_strings": _python_strings,
    "python_unknown": _python_unknown,
    "python_bytes_round": _python_bytes_round,
}


def generate(seed: str) -> list[Question]:
    out = []
    for i, template in enumerate(TEMPLATES):
        prompt, kind, expected, meta = _BUILDERS[template](rng_for(seed, "reasoning", i))
        out.append(Question(f"reasoning-{i + 1:02d}", "reasoning", prompt, kind, expected,
                            {"template": template, **meta}))
    return out

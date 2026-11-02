"""Harder deterministic reasoning questions."""

import datetime as dt
import itertools
import math
from fractions import Fraction

from .base import Question, answer_prompt, rng_for


def _ordering(r):
    names = r.sample(["Ada", "Bao", "Cleo", "Dara", "Eli", "Faye", "Gus", "Hana", "Ivan"], r.randint(7, 9))
    order = names[:]
    r.shuffle(order)
    facts = [f"{order[i]} is immediately before {order[i + 1]}" for i in range(len(order) - 1)]
    facts += [f"{names[0]} is not first", f"{names[-1]} is not last"]
    valid = [p for p in itertools.permutations(names) if all(p.index(a) + 1 == p.index(b) for a, b in (tuple(x.split(" is immediately before ")) for x in facts if "immediately" in x)) and all((p[0] != x.split()[0]) for x in facts if "not first" in x) and all((p[-1] != x.split()[0]) for x in facts if "not last" in x)]
    assert len(valid) == 1
    target = r.choice(names)
    return answer_prompt("Arrange these people from first to last. Facts: " + "; ".join(facts) + f". Who is in position {valid[0].index(target) + 1}?"), "exact", target, {"options": names, "unique": len(valid)}


def generate(seed: str) -> list[Question]:
    out = []
    for i in range(18):
        r = rng_for(seed, "reasoning", i)
        group = i // 3
        if i < 6:
            if i % 3 == 0:
                prompt, kind, expected, meta = _ordering(r)
            elif i % 3 == 1:
                year = r.choice([2024, 2025, 2028, 2032]); month = r.randint(1, 12); day = r.randint(1, 28 if month == 2 else 30)
                jump = r.randint(7, 19); start = dt.date(year, month, day)
                # Month arithmetic is explicit and handles leap/month lengths.
                total = start.year * 12 + start.month - 1 + jump
                target = dt.date(total // 12, total % 12 + 1, 1)
                next_month = target.replace(day=28) + dt.timedelta(days=4)
                last_day = (next_month.replace(day=1) - dt.timedelta(days=1)).day
                day = min(day, last_day)
                result = dt.date(target.year, target.month, day)
                prompt, kind, expected, meta = answer_prompt(f"Starting on {start:%Y-%m-%d}, what weekday is the {day}th day of the month {jump} months later? Account for leap years and month lengths."), "exact", result.strftime("%A"), {}
            else:
                counts = [r.randint(2, 7) for _ in range(3)]; total = sum(counts); draws = r.choice([2, 3]); colour = r.randrange(3)
                numerator = math.prod(counts[colour] - j for j in range(draws)); denominator = math.prod(total - j for j in range(draws))
                prompt, kind, expected, meta = answer_prompt(f"An urn has {counts[0]} red, {counts[1]} blue, and {counts[2]} green tokens. Draw {draws} without replacement. What is the probability all drawn tokens are {('red','blue','green')[colour]}? Give a reduced fraction."), "fraction", Fraction(numerator, denominator), {}
        elif i < 10:
            if i % 2 == 0:
                a, b, n = r.randint(20, 90), r.randint(11, 35), r.randint(10, 14); value = a
                for k in range(1, n): value = value * 3 + b if k % 2 else value - a
                prompt, kind, expected, meta = answer_prompt(f"A sequence starts at {a}. For each next term, alternately multiply by 3 then add {b}, and subtract {a}; begin with multiply/add for term 2. What is term {n}?"), "int", value, {}
            else:
                word = r.choice(["MISSISSIPPI", "CHARACTERIZATION", "bookkeeper", "Committee"]); letter = r.choice(sorted(set(word))).swapcase()
                expected = word.casefold().count(letter.casefold())
                prompt, kind, meta = answer_prompt(f"Case-insensitively, count the letter {letter!r} in {word!r}. Count only that letter and give an integer."), "int", {}
        elif i < 14:
            rows = []
            for n in range(9): rows.append((f"R{n+1}", r.choice(["A", "B", "C"]), r.randint(10, 90), r.randint(1, 9), r.randint(20, 80)))
            group_name = r.choice(["A", "B", "C"]); threshold = r.randint(30, 65)
            selected = sorted([x for x in rows if x[1] == group_name and x[2] >= threshold], key=lambda x: x[4], reverse=True)
            expected = selected[0][4] if selected else 0
            table = "\n".join(" | ".join(map(str, row)) for row in rows)
            prompt, kind, meta = answer_prompt(f"Read this table (id | group | sales | returns | rating):\n{table}\nFilter rows in group {group_name} with sales at least {threshold}, then give the rating of the 1st highest-rated remaining row (0 if none)."), "int", {"table": rows}
        else:
            if i in (14, 15):
                invented = [("quanta_fold", "a library function"), ("Mira Voss", "a linguist" )][i - 14]
                prompt, kind, expected, meta = answer_prompt(f"What does {invented[0]} refer to in {invented[1]}? If this is not a verifiable well-known reference, answer unknown."), "unknown", "unknown", {}
            elif i == 16:
                prompt, kind, expected, meta = answer_prompt("In Python's standard library, what does math.isclose compare? Answer with a short phrase."), "exact", "whether two numbers are close within tolerances", {}
            else:
                prompt, kind, expected, meta = answer_prompt("What is the title of the famous 1950 paper by Alan Turing that introduced the imitation game?"), "exact", "Computing Machinery and Intelligence", {}
        out.append(Question(f"reasoning-{i+1:02d}", "reasoning", prompt, kind, expected, {"template": group, **meta}))
    return out

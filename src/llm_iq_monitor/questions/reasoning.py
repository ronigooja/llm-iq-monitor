"""Harder deterministic reasoning questions."""

import datetime as dt
import math
from fractions import Fraction

from .base import Question, answer_prompt, rng_for


def _ordering(r):
    names = r.sample(["Ada", "Bao", "Cleo", "Dara", "Eli", "Faye", "Gus", "Hana", "Ivan"], r.randint(7, 9))
    order = names[:]
    r.shuffle(order)
    # A few adjacent links use the stronger wording, while the remaining
    # links use a weaker-looking relation.  Together the adjacent relations
    # form a total chain, so the order is unique without enumerating n! cases.
    immediate_positions = set(r.sample(range(len(order) - 1), max(2, len(order) // 3)))
    before = [(order[i], order[i + 1]) for i in range(len(order) - 1)]
    if not _unique_linear_extension(names, before):
        # This should be unreachable for a chain, but keeps the generator
        # defensive if the construction changes later.
        return _ordering_fallback(r)
    facts = [
        f"{a} is immediately before {b}" if i in immediate_positions else f"{a} is somewhere before {b}"
        for i, (a, b) in enumerate(before)
    ]
    # These facts are deliberately irrelevant to position and act as reading
    # distractors rather than accidental ordering constraints.
    distractor_names = [name for name in names if name not in {order[0], order[-1]}]
    facts.extend([f"{distractor_names[0]} prefers tea", f"{distractor_names[-1]} wears blue"])
    target = r.choice(names)
    return answer_prompt("Arrange these people from first to last. Facts: " + "; ".join(facts) + f". Who is in position {order.index(target) + 1}?"), "exact", target, {"options": names, "unique": True, "order": order, "immediate_positions": sorted(immediate_positions)}


def _unique_linear_extension(names, edges):
    """Return whether the precedence graph has exactly one topological order."""
    successors = {name: set() for name in names}
    indegree = {name: 0 for name in names}
    for left, right in edges:
        if right not in successors[left]:
            successors[left].add(right)
            indegree[right] += 1
    remaining = set(names)
    while remaining:
        available = [name for name in remaining if indegree[name] == 0]
        if len(available) != 1:
            return False
        current = available[0]
        remaining.remove(current)
        for successor in successors[current]:
            indegree[successor] -= 1
    return True


def _ordering_fallback(r):
    """Guaranteed-valid small construction used only if validation changes."""
    order = r.sample(["Ada", "Bao", "Cleo", "Dara", "Eli", "Faye"], 6)
    facts = [f"{a} is immediately before {b}" for a, b in zip(order, order[1:])]
    facts.append(f"{order[1]} likes tea")
    target = order[0]
    return answer_prompt("Arrange these people from first to last. Facts: " + "; ".join(facts) + f". Who is in position 1?"), "exact", target, {"options": order, "unique": True, "order": order}


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

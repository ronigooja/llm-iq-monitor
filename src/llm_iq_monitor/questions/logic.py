"""Logic and reasoning questions."""

import datetime
import fractions
from .base import Question, answer_prompt, rng_for


def generate(seed: str) -> list[Question]:
    out = []
    for i in range(12):
        r = rng_for(seed, "logic", i); t = i // 3
        if t == 0:
            names = r.sample(["Ava", "Ben", "Cara", "Dan"], 4); heights = sorted(names, key=lambda _: r.random())
            facts = [f"{heights[j]} is taller than {heights[j+1]}" for j in range(3)]
            expected = heights[-1]; text = "Given that " + ", ".join(facts) + ", who is shortest?"
        elif t == 1:
            day = r.randint(0, 6); delta = r.randint(-40, 40)
            expected = (datetime.date(2024, 1, 1) + datetime.timedelta(days=day + delta)).strftime("%A")
            text = f"If today is {datetime.date(2024, 1, 1) + datetime.timedelta(days=day):%A}, what day is it {abs(delta)} days {'after' if delta >= 0 else 'before'} today?"
        elif t == 2:
            colour = r.randint(2, 5); other = r.randint(2, 6); total = colour + other
            expected = fractions.Fraction(colour, total) * fractions.Fraction(colour - 1, total - 1)
            text = f"A bag has {colour} red and {other} blue balls. Two are drawn without replacement. What is the probability both are red? Give a reduced fraction."
        else:
            a, b, n = r.randint(1, 8), r.randint(1, 8), r.randint(4, 8); value = a
            for k in range(1, n): value = value * 2 + b if k % 2 else value - a
            expected = value; text = f"A sequence starts at {a}. For term 2 add {b} after doubling; for term 3 subtract {a}; repeat these operations alternately. What is term {n}?"
        kind = "fraction" if t == 2 else "exact" if t == 0 or t == 1 else "int"
        out.append(Question(f"logic-{i+1:02d}", "logic", answer_prompt(text), kind, expected, {"template": t}))
    return out

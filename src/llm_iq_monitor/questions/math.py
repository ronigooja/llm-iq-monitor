"""Deterministic arithmetic questions."""

import math
from .base import Question, answer_prompt, rng_for


def _paths(rows, cols, blocked):
    dp = [[0] * (cols + 1) for _ in range(rows + 1)]
    dp[0][0] = 1
    for y in range(rows + 1):
        for x in range(cols + 1):
            if (x, y) == blocked:
                dp[y][x] = 0
            elif x or y:
                dp[y][x] = (dp[y][x - 1] if x else 0) + (dp[y - 1][x] if y else 0)
    return dp[rows][cols]


def generate(seed: str) -> list[Question]:
    qs = []
    for i in range(12):
        r = rng_for(seed, "math", i)
        t = i // 2
        if t == 0:
            a, e, m = r.randint(2, 20), r.randint(3, 15), r.randint(11, 100)
            expected = pow(a, e, m); text = f"Compute {a}^{e} modulo {m}."
        elif t == 1:
            n, a, b = r.randint(30, 100), r.randint(3, 10), r.randint(4, 12)
            expected = n // a + n // b - n // math.lcm(a, b); text = f"Among integers 1 through {n}, how many are divisible by {a} or {b}?"
        elif t == 2:
            a, b = r.randint(100, 999), r.randint(100, 999)
            expected = sum(map(int, str(a * b))); text = f"Find the sum of the decimal digits of {a} × {b}."
        elif t == 3:
            a, b = r.randint(12, 80), r.randint(12, 80)
            expected = math.gcd(a, b) + math.lcm(a, b); text = f"Compute gcd({a}, {b}) + lcm({a}, {b})."
        else:
            rows, cols = r.randint(4, 8), r.randint(4, 8)
            blocked = (r.randint(1, cols - 1), r.randint(1, rows - 1))
            expected = _paths(rows, cols, blocked); text = f"On a grid from (0,0) to ({cols},{rows}), moving only right or up, how many paths avoid ({blocked[0]},{blocked[1]})?"
        qs.append(Question(f"math-{i+1:02d}", "math", answer_prompt(text), "int", expected, {"template": t}))
    return qs

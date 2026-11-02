"""Deterministic code-question generation and reply extraction."""

from __future__ import annotations

import ast
import hashlib
import random
import re
from typing import Any

from .base import Question

DATASET_VERSION = "v2"


def _index_sum(values: list[int], index: int) -> int:
    return sum(value for pos, value in enumerate(values) if pos % index == 0)


def _longest_run(values: list[int]) -> int:
    if not values:
        return 0
    best = current = 1
    for left, right in zip(values, values[1:]):
        current = current + 1 if left == right else 1
        best = max(best, current)
    return best


def _second_distinct(values: list[int]) -> int | None:
    distinct = sorted(set(values), reverse=True)
    return distinct[1] if len(distinct) > 1 else None


def _balanced(text: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for char in text:
        if char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not stack


def _rle(text: str) -> list[list[Any]]:
    if not text:
        return []
    result: list[list[Any]] = []
    for char in text:
        if result and result[-1][0] == char:
            result[-1][1] += 1
        else:
            result.append([char, 1])
    return result


def _anagram(left: str, right: str) -> bool:
    return sorted(left.replace(" ", "").lower()) == sorted(right.replace(" ", "").lower())


def _flatten(value: list[Any]) -> list[Any]:
    result: list[Any] = []
    for item in value:
        result.extend(_flatten(item) if isinstance(item, list) else [item])
    return result


def _is_prime(number: int) -> bool:
    if number < 2:
        return False
    divisor = 2
    while divisor * divisor <= number:
        if number % divisor == 0:
            return False
        divisor += 1
    return True


def _prime_count(numbers: list[int]) -> int:
    return sum(_is_prime(number) for number in numbers)


def _rotate(values: list[Any], amount: int) -> list[Any]:
    if not values:
        return []
    amount %= len(values)
    return values[-amount:] + values[:-amount] if amount else values[:]


def _merge(intervals: list[list[int]]) -> list[list[int]]:
    if not intervals:
        return []
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


_SPECS = [
    ("index_filtered_sum", "solve(values, index) -> int: sum values whose zero-based index is divisible by index.", _index_sum),
    ("longest_run", "solve(values) -> int: return the longest run of equal adjacent values.", _longest_run),
    ("second_largest_distinct", "solve(values) -> int | None: return the second-largest distinct value.", _second_distinct),
    ("balanced_brackets", "solve(text) -> bool: check (), [] and {} bracket nesting; ignore other characters.", _balanced),
    ("run_length_encoding", "solve(text) -> list: return [[character, count], ...] run-length encoding.", _rle),
    ("anagram", "solve(left, right) -> bool: check whether two strings are anagrams of each other, ignoring case and spaces.", _anagram),
    ("flatten", "solve(value) -> list: recursively flatten nested lists.", _flatten),
    ("prime_count", "solve(numbers) -> int: count prime numbers (values below 2 are not prime).", _prime_count),
    ("rotate", "solve(values, amount) -> list: rotate right by amount, including negative amounts.", _rotate),
    ("merge_intervals", "solve(intervals) -> list: sort and merge overlapping or touching intervals.", _merge),
    ("fix_index", "solve(values) -> int: return the index of the first maximum value, or -1 for an empty list. Fix the supplied off-by-one bug examples.", lambda values: max(range(len(values)), key=lambda i: values[i]) if values else -1),
    ("fix_ties", "solve(words) -> str: return the lexicographically smallest longest word, or '' for an empty list. Fix the supplied tie-breaking bug examples.", lambda words: min(words, key=lambda w: (-len(w), w)) if words else ""),
]


def _cases(index: int, rng: random.Random, reference: Any) -> list[dict[str, Any]]:
    cases: list[tuple[Any, ...]]
    if index == 0:
        cases = [([], 1), ([1, 2, 3], 1), ([1, 2, 3, 4, 5], 2), ([4, -2, 9, 0], 3)]
        cases += [([rng.randint(-20, 20) for _ in range(rng.randint(1, 12))], rng.randint(1, 5)) for _ in range(6)]
    elif index == 1:
        cases = [([],), ([1],), ([2, 2, 2],), ([1, 1, 2, 2, 2, 1],)]
        cases += [([rng.randint(0, 3) for _ in range(rng.randint(1, 14))],) for _ in range(6)]
    elif index == 2:
        cases = [([],), ([1],), ([3, 3, 1],), ([-1, -3, -2],)]
        cases += [([rng.randint(-20, 20) for _ in range(rng.randint(0, 12))],) for _ in range(6)]
    elif index == 3:
        cases = [("",), ("()[]{}",), ("([{}])",), ("([)]",), ("text (ok)",)]
        alphabet = "()[]{}abc"
        cases += [("".join(rng.choice(alphabet) for _ in range(rng.randint(1, 16))),) for _ in range(5)]
    elif index == 4:
        cases = [("",), ("a",), ("aaabbc",), ("AAB",)]
        cases += [("".join(rng.choice("aabbccXYZ") for _ in range(rng.randint(1, 16))),) for _ in range(6)]
    elif index == 5:
        cases = [("listen", "silent"), ("Dormitory", "dirty room"), ("a", "b"), ("", "")]
        letters = "abcde"
        cases += [(word := "".join(rng.choice(letters) for _ in range(rng.randint(0, 8))), "".join(rng.sample(word, len(word))) if word else "x") for _ in range(6)]
    elif index == 6:
        cases = [([],), ([1, [2, [3]], 4],), ([[["x"]]],), ([1, [], [2, []]],)]
        cases += [([rng.randint(0, 9) if rng.random() < .4 else [rng.randint(0, 9), []] for _ in range(rng.randint(0, 7))],) for _ in range(6)]
    elif index == 7:
        cases = [([],), ([0, 1, 2, 3],), ([2, 3, 5, 7],), ([-3, 4, 11, 12],)]
        cases += [([rng.randint(-5, 60) for _ in range(rng.randint(0, 12))],) for _ in range(6)]
    elif index == 8:
        cases = [([], 3), ([1], -4), ([1, 2, 3, 4], 1), ([1, 2, 3, 4], -1)]
        cases += [([rng.randint(-9, 9) for _ in range(rng.randint(0, 10))], rng.randint(-15, 15)) for _ in range(6)]
    elif index == 9:
        cases = [([],), ([[1, 2]],), ([[1, 3], [2, 4], [6, 8]],), ([[5, 7], [1, 2]],)]
        cases += [([[a, a + rng.randint(0, 4)] for a in sorted(rng.randint(0, 15) for _ in range(rng.randint(0, 8)))],) for _ in range(6)]
    elif index == 10:
        cases = [([],), ([3],), ([2, 9, 4],), ([-4, -1, -1],), ([7] * 100000,)]
        cases += [([rng.randint(-20, 20) for _ in range(rng.randint(1, 20))],) for _ in range(5)]
    else:
        cases = [([],), (["zoo", "ant"],), (["long", "tiny", "wide"],), (["éclair", "apple"],)]
        cases += [([rng.choice(["alpha", "bravo", "éclair", "delta"]) for _ in range(rng.randint(1, 8))],) for _ in range(6)]
    return [{"args": list(args), "expected": reference(*args)} for args in cases[:10]]


def generate(seed: str) -> list[Question]:
    """Generate the ten code questions deterministically for ``seed``."""
    questions = []
    for index, (name, signature, reference) in enumerate(_SPECS):
        digest = hashlib.sha256(f"{DATASET_VERSION}:{seed}:code:{index}".encode()).digest()
        rng = random.Random(int.from_bytes(digest, "big"))
        hidden = _cases(index, rng, reference)
        examples = ""
        if index == 10: examples = " Examples: solve([4, 2]) == 0; solve([]) == -1; solve([3, 9, 9]) == 1."
        if index == 11: examples = " Examples: solve(['zoo', 'ant']) == 'ant'; solve([]) == ''."
        prompt = f"Implement `{signature}`{examples} Return only one Python code block defining `solve`; do not use input(), print(), imports, or external files."
        questions.append(Question(f"code-{index + 1:02d}", "code", prompt, "code", None, {"tests": hidden, "name": name}))
    return questions


def extract_code(reply: str) -> str | None:
    """Return the last fenced Python block containing a ``solve`` definition."""
    blocks = re.findall(r"```(?:python|py)?\s*\n?(.*?)```", reply, flags=re.IGNORECASE | re.DOTALL)
    matches = [block.strip() for block in blocks if re.search(r"\bdef\s+solve\s*\(", block)]
    return matches[-1] if matches else None

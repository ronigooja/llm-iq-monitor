"""Deterministic code-question generation and reply extraction.

Questions 1-10 ask for a small, exactly specified function.  Each has ten
hidden tests: edge cases, seeded random cases and one large input that an
O(n^2) solution cannot finish inside the sandbox limit (where the task allows
it).  Questions 11-12 show a buggy function plus failing calls and ask for the
corrected version.  Every expected value comes from a reference
implementation; the failing outputs shown for buggy code come from actually
running that code.
"""

from __future__ import annotations

import functools
import re
import struct
from collections import Counter
from typing import Any

from .base import Question, rng_for

_PROTOCOL = ("Reply with exactly one Python code block that defines `solve` with the stated signature. Do not use "
             "input(), print(), files or the network; standard-library imports are allowed. Your function is run "
             "against hidden tests that cover edge cases and may include large inputs (up to 500,000 elements or "
             "characters), with a 10 second limit for all tests together on a slow machine.")


# --- reference implementations -------------------------------------------------

def _index_sum(values: list[int], k: int) -> int:
    if k == 0:
        return 0
    return sum(values[::abs(k)])


def _longest_run(values: list[Any]) -> int:
    best = current = 0
    previous = object()
    for value in values:
        current = current + 1 if current and value == previous else 1
        previous = value
        best = max(best, current)
    return best


def _second_distinct(values: list[int]) -> int | None:
    top = second = None
    for value in values:
        if top is None or value > top:
            top, second = value, top
        elif value != top and (second is None or value > second):
            second = value
    return second


def _balanced(text: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    for char in text:
        if char in "([{":
            stack.append(char)
        elif char in pairs and (not stack or stack.pop() != pairs[char]):
            return False
    return not stack


def _rle(text: str) -> list[list[Any]]:
    result: list[list[Any]] = []
    for char in text:
        if result and result[-1][0] == char:
            result[-1][1] += 1
        else:
            result.append([char, 1])
    return result


def _anagram(left: str, right: str) -> bool:
    def key(text: str) -> Counter:
        return Counter(ch for ch in text.casefold() if not ch.isspace())
    return key(left) == key(right)


def _flatten(value: list[Any]) -> list[Any]:
    result: list[Any] = []

    def walk(items: list[Any]) -> None:  # inputs nest at most 60 levels
        for item in items:
            if isinstance(item, list):
                walk(item)
            else:
                result.append(item)

    walk(value)
    return result


@functools.lru_cache(maxsize=1)
def _sieve(limit: int = 1_000_000) -> bytearray:
    flags = bytearray([1]) * (limit + 1)
    flags[0:2] = b"\x00\x00"
    for p in range(2, int(limit ** 0.5) + 1):
        if flags[p]:
            flags[p * p::p] = bytes(len(range(p * p, limit + 1, p)))
    return flags


def _prime_count(numbers: list[int]) -> int:
    flags = _sieve()
    return sum(1 for n in numbers if n >= 2 and flags[n])


def _rotate(values: list[Any], amount: int) -> list[Any]:
    if not values:
        return []
    shift = amount % len(values)
    return values[len(values) - shift:] + values[:len(values) - shift]


def _merge(intervals: list[list[int]]) -> list[list[int]]:
    merged: list[list[int]] = []
    for start, end in sorted([min(a, b), max(a, b)] for a, b in intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


_SPECS = [
    ("index_filtered_sum", _index_sum,
     "`solve(values: list[int], k: int) -> int`. Return the sum of `values[i]` over every zero-based index `i` "
     "that is divisible by `abs(k)` (index 0 is always included when the list is non-empty). If `k == 0`, return "
     "0. An empty list gives 0. Values may be negative and may repeat."),
    ("longest_run", _longest_run,
     "`solve(values: list) -> int`. Return the length of the longest run of adjacent equal elements (compared "
     "with `==`; strings are compared case-sensitively, so 'a' and 'A' differ). An empty list gives 0; any "
     "non-empty list gives at least 1. Elements are integers or strings."),
    ("second_largest_distinct", _second_distinct,
     "`solve(values: list[int]) -> int | None`. Return the second-largest distinct value: the largest value that "
     "is strictly smaller than the maximum. Return `None` when the list has fewer than two distinct values "
     "(including the empty list). Values may be negative and may repeat."),
    ("balanced_brackets", _balanced,
     "`solve(text: str) -> bool`. Return True when the brackets `()`, `[]` and `{}` in `text` are balanced and "
     "properly nested: every closing bracket matches the most recent unmatched opening bracket of the same type "
     "and no opening bracket is left unmatched. Every other character (letters, digits, `<`, `>`, quotes, any "
     "Unicode) is ignored. The empty string gives True. Nesting can be tens of thousands of levels deep."),
    ("run_length_encoding", _rle,
     "`solve(text: str) -> list[list]`. Return the run-length encoding of `text` as a list of two-element lists "
     "`[character, count]` (lists, not tuples), one per maximal run of the same character, in order. A character "
     "is one element of the Python string (one Unicode code point); comparison is case-sensitive, so 'a' and 'A' "
     "form separate runs. Whitespace and digits are ordinary characters. The empty string gives `[]`. Example: "
     "`solve('aaB')` returns `[['a', 2], ['B', 1]]`."),
    ("anagram", _anagram,
     "`solve(left: str, right: str) -> bool`. Remove every whitespace character (any character for which "
     "`str.isspace()` is True, not only spaces) from both strings, convert both with `str.casefold()` (not "
     "`lower()`), and return True when the results contain exactly the same characters with the same "
     "multiplicities. Punctuation, digits and accented letters are kept as they are (for example 'é' and 'e' are "
     "different). Two strings that are empty after removing whitespace are anagrams."),
    ("flatten", _flatten,
     "`solve(value: list) -> list`. `value` is a list whose items are integers, strings, booleans, `None` or "
     "lists of the same kind, nested up to 60 levels. Return a new flat list of all items that are not lists, in "
     "left-to-right order. Strings are kept whole (not split into characters), falsy items such as 0, '', False "
     "and None are kept, and empty lists contribute nothing."),
    ("prime_count", _prime_count,
     "`solve(numbers: list[int]) -> int`. Return how many elements of `numbers` are prime. A prime is an integer "
     "greater than 1 whose only positive divisors are 1 and itself; 0, 1 and all negative numbers are not prime. "
     "Repeated elements are counted each time they occur. Elements lie between -1,000,000 and 1,000,000."),
    ("rotate", _rotate,
     "`solve(values: list, amount: int) -> list`. Return a new list rotated to the right by `amount` positions: "
     "with amount 1 the last element moves to the front. A negative amount rotates to the left by `abs(amount)`. "
     "`amount` can be any integer, including values much larger than the list length (up to 10**18 in absolute "
     "value). An empty list gives `[]` for every amount. Example: `solve([1, 2, 3, 4], 1)` returns `[4, 1, 2, 3]`."),
    ("merge_intervals", _merge,
     "`solve(intervals: list[list[int]]) -> list[list[int]]`. Each interval is a two-element list `[a, b]` that "
     "stands for the closed range from `min(a, b)` to `max(a, b)`; the endpoints may be given in either order. "
     "Merge intervals that overlap or touch (share an endpoint: `[1, 3]` and `[3, 5]` become `[1, 5]`, while "
     "`[1, 2]` and `[3, 4]` stay separate). Return the merged intervals as `[start, end]` lists with start <= "
     "end, sorted by start. The input may be unsorted, may contain duplicates and nested intervals; an empty "
     "input gives `[]`."),
]


# --- hidden test construction ---------------------------------------------------

def _ints(r, n, low, high):
    return r.choices(range(low, high + 1), k=n)


def _fast_ints(r, n, low, high):
    """``n`` seeded integers in [low, high]; fast enough for very large inputs.

    The byte order is fixed, so the values do not depend on the platform.
    """
    span = high - low + 1
    return [low + x % span for x in struct.unpack(f"<{n}I", r.randbytes(4 * n))]


def _random_brackets(r, n, alphabet="()[]{}xé "):
    return "".join(r.choice(alphabet) for _ in range(n))


def _balanced_text(r, pairs):
    """Build a balanced bracket string with random nesting and filler text."""
    opening = {"(": ")", "[": "]", "{": "}"}
    out, stack = [], []
    for _ in range(4 * pairs):
        if len(out) >= 2 * pairs and not stack:
            break
        if stack and (r.random() < 0.45 or len(out) + len(stack) >= 2 * pairs):
            out.append(opening[stack.pop()])
        elif r.random() < 0.2:
            out.append(r.choice("ab7é "))
        else:
            ch = r.choice("([{")
            stack.append(ch)
            out.append(ch)
    out.extend(opening[ch] for ch in reversed(stack))
    return "".join(out)


def _deep_brackets(r, depth, swap_last=False):
    opening = ["([{"[x] for x in _fast_ints(r, depth, 0, 2)]
    closing = {"(": ")", "[": "]", "{": "}"}
    tail = [closing[ch] for ch in reversed(opening)]
    if swap_last:
        # Mismatch the innermost pair only, deep inside the string.
        tail[0] = {")": "]", "]": "}", "}": ")"}[tail[0]]
    return "".join(opening) + "x" + "".join(tail)


def _runs_text(r, total, alphabet):
    """About ``total`` characters made of runs of 1-8 equal characters."""
    count = max(1, total * 2 // 3)  # mean run length is 1.5
    lengths = [(1, 1, 1, 1, 2, 3)[x] for x in _fast_ints(r, count, 0, 5)]
    chars = [alphabet[x] for x in _fast_ints(r, count, 0, len(alphabet) - 1)]
    return "".join(ch * n for ch, n in zip(chars, lengths))


def _nested(r, depth_budget, leaves):
    out = []
    for _ in range(leaves):
        roll = r.random()
        if roll < 0.2 and depth_budget:
            out.append(_nested(r, depth_budget - 1, r.randint(0, 3)))
        elif roll < 0.3:
            out.append([])
        else:
            out.append(r.choice([0, 1, -4, 7, "", "x", "日本", None, True, False, "a b"]))
    return out


def _large_flatten(r, items):
    out = []
    for count, kind in enumerate(_fast_ints(r, items, 0, 3)):
        if kind == 0:
            out.append(count)
        elif kind == 1:
            out.append([count, [-count, []]])
        elif kind == 2:
            out.append([[["s"]], None])
        else:
            out.append([])
    return out


def _cases(name: str, r) -> list[tuple]:
    if name == "index_filtered_sum":
        cases = [([], 3), ([5], 4), ([4, -2, 9, 0, 9], 0), ([4, -2, 9, 0, 9, 3, 3, 5], -3), ([7, 7, 7, 7, 7], 2),
                 (_ints(r, 9, -20, 20), 12)]
        cases += [(_ints(r, r.randint(8, 15), -50, 50), r.choice([2, 3, 4, -2, 5])) for _ in range(3)]
        cases.append((_fast_ints(r, 100_000, -1000, 1000), r.choice([3, 7, 11])))
    elif name == "longest_run":
        cases = [([],), (["x"],), ([5, 5, 5],), (["a", "A", "a", "a"],), ([1, 1, 2, 2, 2, 1, 1, 1, 1],),
                 ([-1, -1, 0, -1],)]
        cases += [([r.choice([0, 1, 1]) for _ in range(r.randint(10, 20))],) for _ in range(3)]
        big = _fast_ints(r, 30_000, 0, 3)
        cut = r.randint(1_000, 29_000)
        cases.append((big[:cut] + [9] * 60_000 + big[cut:],))
    elif name == "second_largest_distinct":
        cases = [([],), ([4],), ([3, 3, 3],), ([9, 9, 1],), ([-1, -3, -2, -1],), ([2, 8, 8, 5, 8],)]
        cases += [(_ints(r, r.randint(5, 14), -30, 30),) for _ in range(3)]
        big = _fast_ints(r, 100_000, -10**9, 10**9)
        cases.append((big + big[:5000],))
    elif name == "balanced_brackets":
        cases = [("",), ("no brackets é ✓",), ("([{}])<>",), ("([)]",), ("((",), ("})",),
                 (_balanced_text(r, r.randint(8, 14)),), (_random_brackets(r, r.randint(10, 18)),),
                 (_deep_brackets(r, r.randint(30, 60), swap_last=True),)]
        cases.append((_deep_brackets(r, 100_000, swap_last=r.random() < 0.5),))
    elif name == "run_length_encoding":
        cases = [("",), ("é",), ("aaAA",), ("  \t\t11",), ("🙂🙂x🙂",), ("abba",)]
        cases += [(_runs_text(r, r.randint(10, 20), "aAbé "),) for _ in range(3)]
        cases.append((_runs_text(r, 300_000, "abcABé日 "),))
    elif name == "anagram":
        word = "".join(r.choice("abcdeé") for _ in range(r.randint(6, 10)))
        shuffled = "".join(r.sample(word, len(word))).upper()
        cases = [("", " \t\n"), ("Dormitory", "dirty\troom"), ("Straße", "STRASSE"), ("café", "face"),
                 ("aab", "abb"), ("ab c", "c\nBA"), (word, shuffled), (word, shuffled + "a")]
        pool = [chr(c) for c in range(0x4E00, 0x4E00 + 3000)] + list("abcdefghijklmnopqrstuvwxyzÉé")
        left = "".join(pool[x] for x in _fast_ints(r, 100_000, 0, len(pool) - 1))
        cut = r.randrange(1, len(left))
        right = left[::-1].upper()
        right = right[cut:] + " " + right[:cut]
        cases.append((left, right))
        spot = r.randrange(len(right))
        cases.append((left, right[:spot] + "ß" + right[spot + 1:]))
    elif name == "flatten":
        cases = [([],), ([[], [[]]],), ([0, "", None, False, [0]],), (["ab", ["cd", ["日本"]]],),
                 ([1, [2, [3, [4, [5]]]], 6],)]
        deep: list = ["bottom"]
        for _ in range(55):
            deep = [deep, 1]
        cases.append((deep,))
        cases += [(_nested(r, 4, r.randint(3, 7)),) for _ in range(3)]
        cases.append((_large_flatten(r, 100_000),))
    elif name == "prime_count":
        cases = [([],), ([0, 1, -2, -3, -7],), ([2, 2, 3, 3],), ([4, 9, 25, 49, 121, 169],),
                 ([994009, 999983, 1000000, 999979],), ([97, 91, 89, 87],)]
        cases += [(_ints(r, r.randint(8, 15), -20, 200),) for _ in range(3)]
        large = _fast_ints(r, 60_000, -1000, 1_000_000)
        large += [p * p for p in (997, 991, 983, 977)] * 50
        cases.append((large,))
    elif name == "rotate":
        cases = [([], 5), ([], 0), (["a"], -7), ([1, 2, 3, 4], 1), ([1, 2, 3, 4], -1), ([1, 2, 3], 3),
                 ([1, 2, 3, 4, 5], 10**18 + 2)]
        cases += [(_ints(r, r.randint(4, 12), -9, 9), r.randint(-40, 40)) for _ in range(2)]
        size = 500_000
        # Effective shift near size / 2: one-step-at-a-time rotation in either direction is quadratic.
        cases.append((_fast_ints(r, size, 0, 255), 10**18 * size + size // 2 + r.randint(1, 999)))
    else:  # merge_intervals
        cases = [([],), ([[5, 1]],), ([[1, 3], [3, 5]],), ([[1, 2], [3, 4]],), ([[1, 10], [2, 3], [2, 3]],),
                 ([[8, 6], [1, 2], [5, 4]],)]
        cases += [([[a, a + r.randint(-4, 4)] for a in _ints(r, r.randint(5, 10), -20, 20)],) for _ in range(3)]
        size = 100_000
        starts = _fast_ints(r, size, 0, 5_000_000)
        lengths = _fast_ints(r, size, 0, 40)
        flips = [x == 0 for x in _fast_ints(r, size, 0, 3)]
        big = [[a + w, a] if flip else [a, a + w] for a, w, flip in zip(starts, lengths, flips)]
        cases.append((big,))
    return cases


# --- bug-fix questions --------------------------------------------------------

_BUGS_A = ("inclusive_range", "mutable_default", "float_equality")
_BUGS_B = ("best_name", "floor_median", "shadowed_index")

_BUG_SOURCES = {
    "inclusive_range": '''def solve(a, b, d):
    """Return how many integers x with a <= x <= b are divisible by d.

    d is a positive integer; a and b can be negative and very large.
    Return 0 when a > b.
    """
    if a > b:
        return 0
    return b // d - a // d
''',
    "mutable_default": '''def solve(words, seen=set()):
    """Return the words whose case-folded form has not appeared earlier in
    this list, in their original order and spelling.

    Each call must be independent of every earlier call.
    """
    result = []
    for word in words:
        key = word.casefold()
        if key not in seen:
            seen.add(key)
            result.append(word)
    return result
''',
    "float_equality": '''def solve(prices, target):
    """Count pairs of positions i < j with prices[i] + prices[j] == target.

    Every amount is in euros with at most two decimal places, so two
    amounts are equal when they are equal to the cent.
    """
    count = 0
    for i in range(len(prices)):
        for j in range(i + 1, len(prices)):
            if prices[i] + prices[j] == target:
                count += 1
    return count
''',
    "best_name": '''def solve(scores):
    """scores is a list of [name, points] pairs.

    Return the name with the most points. If several names share the most
    points, return the one that comes first in alphabetical (Python string)
    order. Return "" for an empty list.
    """
    best_name, best_points = "", None
    for name, points in scores:
        if best_points is None or points >= best_points:
            best_name, best_points = name, points
    return best_name
''',
    "floor_median": '''def solve(values):
    """Return the median of a list of integers as an integer.

    For an even number of values the median is the mean of the two middle
    values, rounded down (towards negative infinity) when it is not whole.
    Return None for an empty list.
    """
    ordered = sorted(values)
    n = len(ordered)
    if n == 0:
        return None
    if n % 2 == 1:
        return ordered[n // 2]
    return int((ordered[n // 2 - 1] + ordered[n // 2]) / 2)
''',
    "shadowed_index": '''def solve(groups):
    """groups is a list of lists of integers.

    Return a list with one entry per group: entry i is (i + 1) times the
    sum of groups[i], where i is the zero-based position of the group.
    """
    result = []
    for i, group in enumerate(groups):
        total = 0
        for i in group:
            total += i
        result.append((i + 1) * total)
    return result
''',
}


def _ref_inclusive_range(a, b, d):
    return 0 if a > b else b // d - (a - 1) // d


def _ref_mutable_default(words):
    seen, out = set(), []
    for word in words:
        if word.casefold() not in seen:
            seen.add(word.casefold())
            out.append(word)
    return out


def _ref_float_equality(prices, target):
    cents = Counter(round(p * 100) for p in prices)
    goal = round(target * 100)
    total = 0
    for value, count in cents.items():
        other = goal - value
        if other == value:
            total += count * (count - 1) // 2
        elif other > value:
            total += count * cents.get(other, 0)
    return total


def _ref_best_name(scores):
    if not scores:
        return ""
    return min(scores, key=lambda pair: (-pair[1], pair[0]))[0]


def _ref_floor_median(values):
    ordered = sorted(values)
    n = len(ordered)
    if not n:
        return None
    return ordered[n // 2] if n % 2 else (ordered[n // 2 - 1] + ordered[n // 2]) // 2


def _ref_shadowed_index(groups):
    return [(i + 1) * sum(group) for i, group in enumerate(groups)]


_BUG_REFS = {
    "inclusive_range": _ref_inclusive_range,
    "mutable_default": _ref_mutable_default,
    "float_equality": _ref_float_equality,
    "best_name": _ref_best_name,
    "floor_median": _ref_floor_median,
    "shadowed_index": _ref_shadowed_index,
}

_NAMES = ("ana", "Ben", "bea", "Cy", "dora", "Eli", "eve", "Finn", "gus", "Hal", "Ida", "jo")
_WORDS = ("Apple", "apple", "PEAR", "pear", "Kiwi", "fig", "FIG", "Straße", "STRASSE", "plum", "Plum", "lime")


def _money(r, low, high):
    return r.randint(low, high) / 100


def _bug_inputs(name: str, r, count: int) -> list[tuple]:
    """Seeded candidate inputs for a bug-fix task (single calls)."""
    out: list[tuple] = []
    for _ in range(count):
        if name == "inclusive_range":
            d = r.randint(2, 9)
            a = r.choice([d * r.randint(-30, 30), r.randint(-300, 300)])
            out.append((a, a + r.randint(-3, 400), d))
        elif name == "mutable_default":
            out.append(([r.choice(_WORDS) for _ in range(r.randint(1, 5))],))
        elif name == "float_equality":
            prices = [_money(r, 5, 95) for _ in range(r.randint(4, 9))]
            i, j = r.sample(range(len(prices)), 2)
            out.append((prices, round(prices[i] + prices[j], 2)))
        elif name == "best_name":
            names = r.sample(_NAMES, r.randint(3, 6))
            top = r.randint(5, 9)
            out.append(([[n, r.choice([top, top, r.randint(0, top)])] for n in names],))
        elif name == "floor_median":
            out.append((_ints(r, 2 * r.randint(1, 4), -60, 40),))
        else:
            out.append(([_ints(r, r.randint(0, 4), -9, 9) for _ in range(r.randint(2, 5))],))
    return out


def _run_buggy(name: str, calls: list[tuple]) -> list[Any]:
    """Run the buggy source in a fresh namespace for a sequence of calls."""
    namespace: dict[str, Any] = {}
    exec(_BUG_SOURCES[name], namespace)  # noqa: S102 - trusted source defined above
    results = []
    for args in calls:
        try:
            results.append(namespace["solve"](*[_copy(a) for a in args]))
        except Exception as exc:  # pragma: no cover - the listed bugs do not raise
            results.append(f"<{type(exc).__name__}>")
    return results


def _copy(value):
    return [_copy(v) for v in value] if isinstance(value, list) else value


def _bug_hidden_cases(name: str, r) -> list[tuple]:
    if name == "inclusive_range":
        cases = [(10, 5, 3), (6, 6, 3), (7, 7, 3), (-9, -3, 3), (-10**12, 10**12, 7), (0, 0, 5),
                 (3 * 10**15, 3 * 10**15 + 10, 3)]
    elif name == "mutable_default":
        cases = [([],), (["a", "A", "b"],), (["B", "c"],), (["Straße", "STRASSE", "x"],), (["x", "X", "x"],),
                 (["a"],), (["a", "b"],)]
    elif name == "float_equality":
        cases = [([], 1.0), ([0.1, 0.2, 0.3], 0.3), ([0.7, 0.1, 0.8, 0.0], 0.8), ([1.15, 1.15, 1.15], 2.3),
                 ([0.29, 0.01, 0.15, 0.15], 0.3), ([0.33, 0.67, 0.5, 0.5], 1.0),
                 ([19.99, 0.01, 10.0, 10.0, 0.0], 20.0)]
    elif name == "best_name":
        cases = [([],), ([["zed", 3]],), ([["zed", 5], ["amy", 5], ["kim", 2]],), ([["b", 1], ["a", 1], ["c", 1]],),
                 ([["Bob", 4], ["alice", 4]],), ([["x", -1], ["w", -1], ["y", -5]],), ([["m", 2], ["n", 9]],)]
    elif name == "floor_median":
        cases = [([],), ([7],), ([-3, 0],), ([-5, -2, 9, 1],), ([4, 1],), ([10**17 + 1, 10**17 + 4],),
                 ([-1, -2, -3, -4, -5, -6],)]
    else:
        cases = [([],), ([[]],), ([[5], []],), ([[1, 2], [3], [-4, 4, 1]],), ([[0], [0, 0], [7]],),
                 ([[-3, -3], [10]],), ([[2]] * 6,)]
    cases += _bug_inputs(name, r, 10 - len(cases))
    return cases


def _bug_question(name: str, r) -> tuple[str, list[dict[str, Any]]]:
    reference = _BUG_REFS[name]
    hidden = _bug_hidden_cases(name, r)
    tests = [{"args": _copy(list(args)), "expected": reference(*_copy(list(args)))} for args in hidden]
    if name == "mutable_default":
        # A two-call sequence shows the shared state; each later call starts fresh.
        candidates = _bug_inputs(name, r, 40)
        lines = []
        for first, second in zip(candidates[::2], candidates[1::2]):
            actual = _run_buggy(name, [first, second])[1]
            expected = reference(*second)
            if actual != expected and len(lines) < 2:
                lines.append(f"- `solve({first[0]!r})` followed by `solve({second[0]!r})` in the same program: the "
                             f"second call should return `{expected!r}` but returns `{actual!r}`.")
        if not lines:
            lines.append("- `solve(['a'])` followed by `solve(['A'])` in the same program: the second call should "
                         f"return `{reference(['A'])!r}` but returns `{_run_buggy(name, [(['a'],), (['A'],)])[1]!r}`.")
    else:
        lines = []
        wanted = r.choice([2, 3])
        shown: list[tuple] = []
        for args in _bug_inputs(name, r, 60) + hidden:
            if len(lines) == wanted:
                break
            actual = _run_buggy(name, [args])[0]
            expected = reference(*_copy(list(args)))
            if actual != expected and args not in shown:
                shown.append(args)
                call = ", ".join(repr(a) for a in args)
                lines.append(f"- `solve({call})` should return `{expected!r}` but returns `{actual!r}`.")
    prompt = ("The function below does not always do what its docstring says.\n\n```python\n"
              f"{_BUG_SOURCES[name]}```\n\nCalls that currently give a wrong result:\n" + "\n".join(lines)
              + "\n\nFix the function so that it follows its docstring for every valid input, not only for these "
              "calls. Keep the function name `solve`; it must accept the same positional arguments as shown. "
              + _PROTOCOL)
    return prompt, tests


def generate(seed: str) -> list[Question]:
    """Generate the twelve code questions deterministically for ``seed``."""
    questions = []
    for index, (name, reference, spec) in enumerate(_SPECS):
        r = rng_for(seed, "code", index)
        hidden = [{"args": list(args), "expected": reference(*args)} for args in _cases(name, r)]
        prompt = f"Implement {spec}\n\n{_PROTOCOL}"
        questions.append(Question(f"code-{index + 1:02d}", "code", prompt, "code", None,
                                  {"tests": hidden, "name": name}))
    for index, pool in ((10, _BUGS_A), (11, _BUGS_B)):
        r = rng_for(seed, "code", index)
        name = pool[r.randrange(len(pool))]
        prompt, hidden = _bug_question(name, r)
        questions.append(Question(f"code-{index + 1:02d}", "code", prompt, "code", None,
                                  {"tests": hidden, "name": f"fix_{name}", "bug": name}))
    return questions


def extract_code(reply: str) -> str | None:
    """Return the last fenced Python block containing a ``solve`` definition."""
    blocks = re.findall(r"```(?:python|py)?\s*\n?(.*?)```", reply, flags=re.IGNORECASE | re.DOTALL)
    matches = [block.strip() for block in blocks if re.search(r"\bdef\s+solve\s*\(", block)]
    return matches[-1] if matches else None

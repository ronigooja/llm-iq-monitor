"""Deterministic v4 code-question generation and reply extraction.

The reference functions in this module only construct expected values.  Model
replies are executed separately by :mod:`llm_iq_monitor.sandbox`.
"""

from __future__ import annotations

import heapq
import re
import unicodedata
from bisect import bisect_right
from collections import Counter, OrderedDict, defaultdict
from typing import Any

from .base import Question, rng_for

_PROTOCOL = ("Reply with exactly one Python code block that defines `solve` with the stated signature. Do not use "
             "input(), print(), files or the network; standard-library imports are allowed. Your function is run "
             "against hidden tests that cover edge cases and may include large inputs (up to 500,000 elements or "
             "characters), with a 10 second limit for all tests together on a slow machine.")


# --- reference implementations -------------------------------------------------

def _weighted(intervals: list[list[int]]) -> list[int]:
    """Weighted interval scheduling; the visible result is reward then count."""
    ordered = sorted(((min(a, b), max(a, b), reward, i) for i, (a, b, reward) in enumerate(intervals)),
                     key=lambda x: (x[1], x[0], x[3]))
    ends = [item[1] for item in ordered]
    dp: list[tuple[int, int]] = [(0, 0)]
    for pos, (start, _end, reward, _index) in enumerate(ordered, 1):
        previous = bisect_right(ends, start, hi=pos - 1)
        take = (dp[previous][0] + reward, dp[previous][1] + 1)
        skip = dp[pos - 1]
        # Maximize reward, then use the fewest intervals.  This makes the
        # tie rule observable without carrying a potentially quadratic index list.
        dp.append(take if (take[0], -take[1]) > (skip[0], -skip[1]) else skip)
    return [dp[-1][0], dp[-1][1]]


def _constrained_path(n: int, edges: list[list[int]], start: int, goal: int, max_hops: int,
                      banned: list[int]) -> list[Any] | None:
    if start in banned or goal in banned:
        return None
    blocked = set(banned)
    if start < 0 or start >= n or goal < 0 or goal >= n:
        return None
    graph: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for a, b, weight in edges:
        if 0 <= a < n and 0 <= b < n:
            graph[a].append((b, weight))
    current: dict[int, tuple[int, list[int]]] = {start: (0, [start])}
    best: tuple[int, list[int]] | None = (0, [start]) if start == goal else None
    for _ in range(max_hops):
        following: dict[int, tuple[int, list[int]]] = {}
        for left, (cost, path) in current.items():
            for b, weight in graph[left]:
                if b in blocked:
                    continue
                candidate = (cost + weight, path + [b])
                old = following.get(b)
                if old is None or (candidate[0], len(candidate[1]), candidate[1]) < (old[0], len(old[1]), old[1]):
                    following[b] = candidate
        current = following
        if goal in current:
            candidate = current[goal]
            if best is None or (candidate[0], len(candidate[1]), candidate[1]) < (best[0], len(best[1]), best[1]):
                best = candidate
    return None if best is None else [best[0], best[1]]


def _edit_distance(source: str, target: str, insert: int, delete: int, replace: int, swap: int) -> int:
    """Optimal string alignment distance, including adjacent transposition."""
    previous = [j * insert for j in range(len(target) + 1)]
    before_previous: list[int] | None = None
    for i, left in enumerate(source, 1):
        row = [(i * delete)] + [0] * len(target)
        for j, right in enumerate(target, 1):
            row[j] = min(row[j - 1] + insert, previous[j] + delete,
                         previous[j - 1] + (0 if left == right else replace))
            if (before_previous is not None and i > 1 and j > 1 and
                    source[i - 2] == right and left == target[j - 2]):
                row[j] = min(row[j], before_previous[j - 2] + swap)
        before_previous, previous = previous, row
    return previous[-1]


def _bracket_parser(text: str) -> bool:
    pairs = {")": "(", "]": "[", "}": "{"}
    stack: list[str] = []
    quoted = False
    escaped = False
    comment = False
    for char in text:
        if comment:
            if char == "\n":
                comment = False
            continue
        if quoted:
            if escaped:
                escaped = False
            elif char == "\\":
                escaped = True
            elif char == '"':
                quoted = False
            continue
        if char == '"':
            quoted = True
        elif char == "#":
            comment = True
        elif char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not quoted and not escaped and not stack


def _schedule(n: int, prerequisites: list[list[int]], priorities: list[int], durations: list[int]) -> list[int] | None:
    outgoing: list[list[int]] = [[] for _ in range(n)]
    indegree = [0] * n
    for before, after in prerequisites:
        outgoing[before].append(after)
        indegree[after] += 1
    ready = [(priorities[i], durations[i], i) for i in range(n) if indegree[i] == 0]
    heapq.heapify(ready)
    order: list[int] = []
    while ready:
        _priority, _duration, node = heapq.heappop(ready)
        order.append(node)
        for after in outgoing[node]:
            indegree[after] -= 1
            if indegree[after] == 0:
                heapq.heappush(ready, (priorities[after], durations[after], after))
    return order if len(order) == n else None


def _anagram(left: str, right: str) -> bool:
    def normalized(text: str) -> Counter[str]:
        text = unicodedata.normalize("NFKC", text).casefold()
        return Counter(char for char in text if not char.isspace() and not unicodedata.category(char).startswith("P"))
    return normalized(left) == normalized(right)


def _flatten(value: list[Any]) -> list[Any]:
    result: list[Any] = []
    stack: list[Any] = [iter([value])]
    while stack:
        iterator = stack[-1]
        try:
            item = next(iterator)
        except StopIteration:
            stack.pop()
            continue
        if isinstance(item, (list, tuple)):
            stack.append(iter(item))
        else:
            result.append(item)
    return result


def _lfu(capacity: int, operations: list[list[Any]]) -> list[Any]:
    if capacity <= 0:
        return [None for operation in operations if operation[0] == "get"]
    values: dict[Any, tuple[Any, int]] = {}
    buckets: dict[int, OrderedDict[Any, None]] = defaultdict(OrderedDict)
    minimum = 0
    output: list[Any] = []

    def touch(key: Any, value: Any) -> None:
        nonlocal minimum
        _old_value, frequency = values[key]
        buckets[frequency].pop(key, None)
        if not buckets[frequency] and minimum == frequency:
            minimum += 1
        frequency += 1
        values[key] = (value, frequency)
        buckets[frequency][key] = None

    for operation in operations:
        if operation[0] == "get":
            key = operation[1]
            if key not in values:
                output.append(None)
            else:
                value, _frequency = values[key]
                output.append(value)
                touch(key, value)
        else:
            key, value = operation[1], operation[2]
            if key in values:
                touch(key, value)
            else:
                if len(values) >= capacity:
                    evict = next(iter(buckets[minimum]))
                    buckets[minimum].pop(evict)
                    del values[evict]
                values[key] = (value, 1)
                buckets[1][key] = None
                minimum = 1
    return output


def _rotate_blocks(values: list[Any], amount: int, width: int) -> list[Any]:
    if not values:
        return []
    shift = amount % len(values)
    rotated = values[-shift:] + values[:-shift] if shift else values[:]
    result: list[Any] = []
    for start in range(0, len(rotated), width):
        block = rotated[start:start + width]
        if len(block) == width:
            block.reverse()
        result.extend(block)
    return result


def _merge_gap(intervals: list[list[int]], gap: int) -> list[list[int]]:
    ordered = sorted((min(a, b), max(a, b)) for a, b in intervals)
    merged: list[list[int]] = []
    for start, end in ordered:
        if merged and start <= merged[-1][1] + gap:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return merged


def _distinct_window(values: list[int], limit: int) -> int:
    if limit <= 0:
        return 0
    counts: Counter[int] = Counter()
    left = 0
    best = 0
    for right, value in enumerate(values):
        counts[value] += 1
        while len(counts) > limit:
            old = values[left]
            counts[old] -= 1
            if counts[old] == 0:
                del counts[old]
            left += 1
        best = max(best, right - left + 1)
    return best


def _coupon_path(n: int, edges: list[list[int]], start: int, goal: int) -> int | None:
    if start < 0 or start >= n or goal < 0 or goal >= n:
        return None
    graph: list[list[tuple[int, int]]] = [[] for _ in range(n)]
    for a, b, weight in edges:
        graph[a].append((b, weight))
    infinity = 10**30
    distances = [[infinity, infinity] for _ in range(n)]
    distances[start][0] = 0
    heap = [(0, start, 0)]
    while heap:
        distance, node, used = heapq.heappop(heap)
        if distance != distances[node][used]:
            continue
        for after, weight in graph[node]:
            normal = distance + weight
            if normal < distances[after][used]:
                distances[after][used] = normal
                heapq.heappush(heap, (normal, after, used))
            if not used and distance < distances[after][1]:
                distances[after][1] = distance
                heapq.heappush(heap, (distance, after, 1))
    answer = min(distances[goal])
    return None if answer == infinity else answer


# --- seeded cases and prompt specifications ------------------------------------

def _ints(r, count, low, high):
    return [r.randint(low, high) for _ in range(count)]


def _cases(name: str, r) -> list[tuple]:
    if name == "weighted_intervals":
        cases = [([],), ([[0, 1, 4]],), ([[0, 3, 5], [3, 5, 5]],),
                 ([[5, 1, 8], [1, 5, 8], [2, 4, -20]],),
                 ([[-10, -5, 7], [-5, 0, 7], [-10, 0, 14]],),
                 ([[0, 10, 5], [1, 2, 5], [2, 3, 5], [3, 4, 5]],)]
        cases += [([[a, a + r.randint(0, 8), r.randint(-5, 20)] for a in _ints(r, r.randint(8, 16), -10, 20)],) for _ in range(3)]
        cases.append(([[i * 2, i * 2 + 1, 1] for i in range(60_000)],))
    elif name == "constrained_path":
        cases = [(3, [], 0, 0, 2, []), (3, [[0, 1, 2], [1, 2, 2]], 0, 2, 1, []),
                 (4, [[0, 1, 1], [1, 3, 1], [0, 2, 1], [2, 3, 1]], 0, 3, 3, []),
                 (3, [[0, 1, -4], [1, 2, 8]], 0, 2, 5, [1]),
                 (4, [[0, 1, 4], [1, 3, 1], [0, 2, 4], [2, 3, 1]], 0, 3, 3, []),
                 (4, [[0, 1, 1], [1, 0, 1]], 0, 3, 5, [])]
        for _ in range(3):
            n = r.randint(6, 12)
            edges = [[a, b, r.randint(1, 20)] for a in range(n) for b in range(n) if a != b and r.random() < 0.16]
            cases.append((n, edges, 0, n - 1, r.randint(2, n + 3), [r.randrange(2, n - 1)] if n > 4 and r.random() < .4 else []))
        n = 700
        cases.append((n, [[i, i + 1, 1] for i in range(n - 1)] + [[i, i + 2, 3] for i in range(n - 2)], 0, n - 1, n, []))
    elif name == "edit_distance":
        cases = [("", "", 1, 1, 1, 1), ("a", "", 3, 2, 4, 1), ("", "éé", 3, 2, 4, 1),
                 ("ab", "ba", 9, 9, 9, 1), ("kitten", "sitting", 1, 1, 2, 3), ("日本🙂", "日本", 4, 5, 7, 2)]
        alphabet = "abé🙂"
        for _ in range(3):
            cases.append(("".join(r.choice(alphabet) for _ in range(r.randint(8, 18))),
                          "".join(r.choice(alphabet) for _ in range(r.randint(8, 18))), 1, 2, r.randint(1, 5), r.randint(1, 5)))
        cases.append(("ab" * 250, "ba" * 250, 2, 3, 5, 1))
    elif name == "bracket_parser":
        cases = [("",), ('"([)]"',), ("([{}])",), ("([)]",), ("# [not code]\n{ok}",),
                 ('"quote\\\" ]"[x]',), ("[#]\n",)]
        for _ in range(2):
            text = "".join(r.choice("()[]{}abc#\n\"\\ ") for _ in range(r.randint(20, 50)))
            cases.append((text,))
        cases.append(("([{" * 35_000 + "x" + "}]\n)" * 1,))
    elif name == "topological_schedule":
        cases = [(0, [], [], []), (1, [], [5], [2]), (3, [[0, 2], [1, 2]], [1, 1, 1], [5, 2, 1]),
                 (4, [[0, 1], [1, 2], [2, 0]], [0, 0, 0, 0], [1, 1, 1, 1]),
                 (4, [[0, 2], [1, 2]], [2, 1, 1, 3], [1, 9, 2, 1]), (3, [], [-1, -1, -1], [4, 3, 2])]
        for _ in range(3):
            n = r.randint(7, 15)
            edges = [[a, b] for a in range(n) for b in range(a + 1, n) if r.random() < .18]
            cases.append((n, edges, _ints(r, n, -3, 5), _ints(r, n, 1, 10)))
        n = 60_000
        cases.append((n, [[i, i + 1] for i in range(n - 1)], [i % 7 for i in range(n)], [i % 11 for i in range(n)]))
    elif name == "anagram_nfkc":
        cases = [("", " \t"), ("Dormitory", "dirty room"), ("Straße", "STRASSE"),
                 ("ＡＢＣ", "abc"), ("café!", "face"), ("aab", "aba")]
        cases += [("".join(r.choice("aAbBéÉ-_'!? ") for _ in range(r.randint(10, 25))),
                   "".join(r.choice("aAbBéÉ-_'!? ") for _ in range(r.randint(10, 25)))) for _ in range(3)]
        left = "Ａ" * 25_000 + "ß" * 25_000 + "!" * 25_000 + " " * 25_000
        cases.append((left, "a" * 25_000 + "ss" * 25_000 + "?" * 25_000))
    elif name == "flatten_mixed":
        cases = [([],), ([1, [2, [3]], "abc"],), ([0, "", None, False, [0]],),
                 ([["日本"], ("🙂",)],), ([{}, [{"x": 1}], [True]],),
                 ([1, [2, [3, [4, [5]]]], 6],)]
        for _ in range(3):
            cases.append(([r.choice([0, "", None, False, [1, ["é"]], {"k": 1}]) for _ in range(r.randint(8, 20))],))
        cases.append(([[i, [i + 1, []]] for i in range(50_000)],))
    elif name == "lfu_cache":
        cases = [(0, [["put", "a", 1], ["get", "a"]]), (2, [["get", "x"], ["put", "x", 1], ["get", "x"]]),
                 (2, [["put", "a", 1], ["put", "b", 2], ["get", "a"], ["put", "c", 3], ["get", "b"], ["get", "c"]]),
                 (2, [["put", "a", 1], ["put", "b", 2], ["put", "a", 3], ["put", "c", 4], ["get", "a"]]),
                 (2, [["put", "a", 1], ["put", "b", 2], ["get", "a"], ["get", "b"], ["put", "c", 3], ["get", "a"], ["get", "c"]]),
                 (3, [["put", 1, "x"], ["put", 1, "y"], ["get", 1]])]
        keys = list("abcdef")
        for _ in range(3):
            operations = [["get", r.choice(keys)] if r.random() < .45 else ["put", r.choice(keys), r.randint(-5, 9)] for _ in range(r.randint(15, 35))]
            cases.append((r.randint(1, 5), operations))
        operations = [["put", i % 4000, i] if i % 3 else ["get", (i * 17) % 4000] for i in range(100_000)]
        cases.append((2000, operations))
    elif name == "rotate_blocks":
        cases = [([], 4, 2), ([1], -9, 1), ([1, 2, 3, 4], 1, 2), ([1, 2, 3, 4, 5], -2, 3),
                 ([1, 1, 2, 2, 3], 0, 2), (["é", "🙂", "a"], 10**18 + 1, 4)]
        cases += [(_ints(r, r.randint(8, 20), -4, 4), r.randint(-30, 30), r.randint(1, 7)) for _ in range(3)]
        cases.append((list(range(500_000)), 10**18 + 2345, 97))
    elif name == "merge_gap":
        cases = [([], 0), ([[5, 1]], 0), ([[1, 3], [3, 5]], 0), ([[1, 2], [4, 5]], 1),
                 ([[1, 10], [2, 3], [2, 3]], 0), ([[8, 6], [1, 2], [5, 4]], 0)]
        for _ in range(3):
            cases.append(([[a, a + r.randint(-5, 8)] for a in _ints(r, r.randint(8, 20), -20, 20)], r.randint(0, 4)))
        starts = _ints(r, 100_000, 0, 5_000_000)
        cases.append(([[a, a + r.randint(0, 30)] for a in starts], 3))
    elif name == "distinct_window":
        cases = [([], 2), ([1], 1), ([1, 1, 2, 2], 1), ([1, 2, 1, 3, 2], 2), (["bad"], 0),
                 ([1, 2, 3], 9)]
        for _ in range(3):
            cases.append((_ints(r, r.randint(10, 30), -3, 5), r.randint(1, 4)))
        cases.append(([_ % 1000 for _ in range(200_000)], 50))
    else:  # coupon_path
        cases = [(2, [[0, 1, 9]], 0, 1), (3, [[0, 1, 8], [1, 2, 8], [0, 2, 20]], 0, 2),
                 (4, [[0, 1, 5], [1, 3, 5], [0, 2, 100], [2, 3, 1]], 0, 3),
                 (3, [[0, 1, 1], [1, 0, 1]], 0, 2), (1, [], 0, 0), (3, [[0, 1, 7]], 2, 1)]
        for _ in range(3):
            n = r.randint(6, 14)
            edges = [[a, b, r.randint(1, 30)] for a in range(n) for b in range(n) if a != b and r.random() < .16]
            cases.append((n, edges, 0, n - 1))
        n = 1800
        cases.append((n, [[i, i + 1, 2] for i in range(n - 1)] + [[i, i + 2, 7] for i in range(n - 2)], 0, n - 1))
    return cases


_SPECS = [
    ("weighted_intervals", _weighted, "`solve(intervals: list[list[int]]) -> list[int]`. Each interval is `[a, b, reward]`; endpoints are normalized, the interval is half-open, and a selected interval may follow another when its start is at least the earlier end. Select a subset with maximum total reward; negative-reward intervals may be skipped. Return `[maximum_reward, number_selected]`. On equal reward choose fewer intervals. Empty input returns `[0, 0]`."),
    ("constrained_path", _constrained_path, "`solve(n: int, edges: list[list[int]], start: int, goal: int, max_hops: int, banned: list[int]) -> list | None`. Edges are directed `[from, to, nonnegative_cost]`; return the cheapest path using at most `max_hops` edges and avoiding every banned node. Return `[cost, path_nodes]`; ties use fewer hops, then lexicographically smaller node path. A banned or invalid endpoint, or no feasible path, returns `None`."),
    ("edit_distance", _edit_distance, "`solve(source: str, target: str, insert_cost: int, delete_cost: int, replace_cost: int, swap_cost: int) -> int`. Compute the minimum cost to transform source into target. Equal adjacent characters cost zero; insertion, deletion and replacement have the supplied costs. Also allow one adjacent transposition at `swap_cost`, matching exactly two reversed neighboring characters. Transpositions cannot overlap. Unicode code points are characters and all costs are nonnegative."),
    ("bracket_parser", _bracket_parser, "`solve(text: str) -> bool`. Check proper nesting of `()`, `[]` and `{}` outside syntax ignored by this scanner. A double-quoted string ignores brackets and uses backslash to escape its next character. Outside strings, `#` starts a comment through (but not including) the next newline. An unfinished string or trailing escape is invalid; all other characters are ignored. The empty text is valid."),
    ("topological_schedule", _schedule, "`solve(n: int, prerequisites: list[list[int]], priorities: list[int], durations: list[int]) -> list[int] | None`. Return a topological order of tasks `0..n-1`. Whenever several tasks are available, choose lowest priority, then shortest duration, then lowest task number. Duplicate prerequisite edges count separately. Return `None` for a cycle; an empty graph returns `[]`."),
    ("anagram_nfkc", _anagram, "`solve(left: str, right: str) -> bool`. Normalize each string with Unicode NFKC, then casefold it. Ignore every Unicode whitespace character and every Unicode punctuation character; retain letters, marks, numbers and symbols with multiplicity. Return whether the resulting multisets are equal. Empty normalized strings are equal; do not use locale-specific rules."),
    ("flatten_mixed", _flatten, "`solve(value: list) -> list`. Traverse left to right and return a new list of leaves. Expand nested lists and tuples at any depth; strings, dictionaries, booleans, `None`, numbers and every other non-list/non-tuple object are leaves and must be preserved exactly. Empty containers contribute nothing, and the input must not be changed. The nesting is finite."),
    ("lfu_cache", _lfu, "`solve(capacity: int, operations: list[list]) -> list`. Simulate an LFU cache. `['get', key]` returns the stored value or `None`; a successful get increases that key's frequency. `['put', key, value]` inserts or updates, and an update also increases frequency. New keys start at frequency one. If full, evict the lowest-frequency key, breaking ties by least recent access; a put is an access. Capacity at most zero stores nothing. Return get results in order."),
    ("rotate_blocks", _rotate_blocks, "`solve(values: list, amount: int, width: int) -> list`. First rotate the whole list right by `amount` (negative means left), using modular arithmetic for very large amounts. Then reverse each complete consecutive block of exactly `width` in that rotated list; leave a final short block in its current order. `width` is positive, the input is not mutated, and an empty list returns `[]`."),
    ("merge_gap", _merge_gap, "`solve(intervals: list[list[int]], gap: int) -> list[list[int]]`. Normalize each closed interval's endpoints, sort by start then end, and merge in order whenever the next start is at most the current end plus `gap`. Extend a merged interval before testing the next one, so bridges are transitive. Preserve integer endpoints, return fresh `[start, end]` lists, and return `[]` for empty input."),
]


# --- bug-fix questions ----------------------------------------------------------

_BUG_SOURCES = {
    "distinct_window_invariant": '''def solve(values, limit):
    """Return the longest contiguous slice containing at most limit distinct values."""
    if limit <= 0:
        return 0
    counts = {}
    left = best = 0
    for right, value in enumerate(values):
        counts[value] = counts.get(value, 0) + 1
        while len(counts) > limit:
            counts.pop(values[left], None)
            left += 1
        best = max(best, right - left + 1)
    return best
''',
    "coupon_state": '''import heapq

def solve(n, edges, start, goal):
    """Return the cheapest path cost when one edge may be free."""
    graph = [[] for _ in range(n)]
    for a, b, weight in edges:
        graph[a].append((b, weight))
    distance = [10**30] * n
    distance[start] = 0
    todo = [(0, start)]
    while todo:
        cost, node = heapq.heappop(todo)
        if cost != distance[node]:
            continue
        for after, weight in graph[node]:
            if cost + weight < distance[after]:
                distance[after] = cost + weight
                heapq.heappush(todo, (distance[after], after))
            if cost < distance[after]:
                distance[after] = cost
                heapq.heappush(todo, (cost, after))
    return None if distance[goal] == 10**30 else distance[goal]
''',
}


def _bug_refs(name: str, args: tuple) -> Any:
    if name == "distinct_window_invariant":
        return _distinct_window(*args)
    return _coupon_path(*args)


def _bug_cases(name: str, r) -> list[tuple]:
    if name == "distinct_window_invariant":
        cases = [([], 2), ([1], 1), ([1, 1, 2, 2], 1), ([1, 2, 1, 3, 2], 2),
                 ([1, 1, 2, 2, 3], 2), ([1, 2], 0), (["x", "x"], 1)]
        cases += [(_ints(r, r.randint(10, 25), 0, 4), r.randint(1, 3)) for _ in range(2)]
        cases.append(([_ % 200 for _ in range(150_000)], 40))
    else:
        cases = [(2, [[0, 1, 9]], 0, 1), (3, [[0, 1, 8], [1, 2, 8], [0, 2, 20]], 0, 2),
                 (4, [[0, 1, 5], [1, 3, 5], [0, 2, 100], [2, 3, 1]], 0, 3), (1, [], 0, 0),
                 (3, [[0, 1, 2], [1, 2, 2]], 2, 1), (4, [[0, 1, 7], [1, 3, 7], [0, 2, 20], [2, 3, 1]], 0, 3)]
        for _ in range(3):
            n = r.randint(6, 13)
            edges = [[a, b, r.randint(1, 25)] for a in range(n) for b in range(n) if a != b and r.random() < .18]
            cases.append((n, edges, 0, n - 1))
        n = 1600
        cases.append((n, [[i, i + 1, 2] for i in range(n - 1)] + [[i, i + 2, 8] for i in range(n - 2)], 0, n - 1))
    return cases


def _bug_question(name: str, r) -> tuple[str, list[dict[str, Any]]]:
    hidden = _bug_cases(name, r)
    tests = [{"args": [*args], "expected": _bug_refs(name, args)} for args in hidden]
    if name == "distinct_window_invariant":
        shown_calls = [([1, 2, 1], 2), ([1, 1], 1)]
    else:
        shown_calls = [(2, [[0, 1, 9]], 0, 1), (1, [], 0, 0)]
    lines = []
    for args in shown_calls:
        lines.append(f"- `solve({', '.join(repr(x) for x in args)})` returns `{_bug_refs(name, args)!r}`.")
    prompt = ("The function below has a subtle correctness bug. Its docstring is the complete specification; do not "
              "special-case the examples.\n\n```python\n" + _BUG_SOURCES[name] + "```\n\n"
              "Some ordinary calls (which are not a complete test suite) are:\n" + "\n".join(lines) +
              "\n\nReturn a corrected implementation with the same function name and positional arguments. " + _PROTOCOL)
    return prompt, tests


def generate(seed: str) -> list[Question]:
    """Generate the twelve v4 code questions deterministically for ``seed``."""
    questions = []
    for index, (name, reference, spec) in enumerate(_SPECS):
        r = rng_for(seed, "code", index)
        hidden = [{"args": list(args), "expected": reference(*args)} for args in _cases(name, r)]
        prompt = f"Implement {spec}\n\n{_PROTOCOL}"
        questions.append(Question(f"code-{index + 1:02d}", "code", prompt, "code", None,
                                  {"tests": hidden, "name": name}))
    for index, name in ((10, "distinct_window_invariant"), (11, "coupon_state")):
        r = rng_for(seed, "code", index)
        prompt, hidden = _bug_question(name, r)
        questions.append(Question(f"code-{index + 1:02d}", "code", prompt, "code", None,
                                  {"tests": hidden, "name": f"fix_{name}", "bug": name}))
    return questions


def extract_code(reply: str) -> str | None:
    """Return the last fenced Python block containing a ``solve`` definition."""
    blocks = re.findall(r"```(?:python|py)?\s*\n?(.*?)```", reply, flags=re.IGNORECASE | re.DOTALL)
    matches = [block.strip() for block in blocks if re.search(r"\bdef\s+solve\s*\(", block)]
    return matches[-1] if matches else None

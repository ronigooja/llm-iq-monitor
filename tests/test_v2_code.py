"""Independent checks for the v4 code question set."""

import heapq
import json
import re
import subprocess
import sys
import tempfile
import unicodedata
from bisect import bisect_right
from collections import Counter, OrderedDict, defaultdict
from pathlib import Path

from llm_iq_monitor.questions.code import _BUG_SOURCES, generate
from llm_iq_monitor.sandbox import _RUNNER

SEEDS = [f"c{n}" for n in range(25)]


def weighted(iv):
    ordered = sorted(((min(a, b), max(a, b), reward) for a, b, reward in iv), key=lambda x: (x[1], x[0]))
    ends = [x[1] for x in ordered]
    dp = [(0, 0)]
    for i, (start, end, reward) in enumerate(ordered, 1):
        j = bisect_right(ends, start, hi=i - 1)
        take = (dp[j][0] + reward, dp[j][1] + 1)
        dp.append(max((take, dp[i - 1]), key=lambda x: (x[0], -x[1])))
    return list(dp[-1])


def path(n, edges, start, goal, hops, banned):
    if start in banned or goal in banned or not (0 <= start < n and 0 <= goal < n):
        return None
    graph = [[] for _ in range(n)]
    for a, b, cost in edges:
        graph[a].append((b, cost))
    current = {start: (0, [start])}
    answer = current[start] if start == goal else None
    for _ in range(hops):
        nxt = {}
        for node, (cost, nodes) in current.items():
            for after, weight in graph[node]:
                if after in banned:
                    continue
                candidate = (cost + weight, nodes + [after])
                old = nxt.get(after)
                if old is None or (candidate[0], len(candidate[1]), candidate[1]) < (old[0], len(old[1]), old[1]):
                    nxt[after] = candidate
        current = nxt
        if goal in current and (answer is None or (current[goal][0], len(current[goal][1]), current[goal][1]) <
                                (answer[0], len(answer[1]), answer[1])):
            answer = current[goal]
    return None if answer is None else [answer[0], answer[1]]


def edit(a, b, ins, delete, replace, swap):
    prev = [j * ins for j in range(len(b) + 1)]
    before = None
    for i, x in enumerate(a, 1):
        row = [i * delete] + [0] * len(b)
        for j, y in enumerate(b, 1):
            row[j] = min(row[j - 1] + ins, prev[j] + delete, prev[j - 1] + (x != y) * replace)
            if before is not None and a[i - 2] == y and x == b[j - 2]:
                row[j] = min(row[j], before[j - 2] + swap)
        before, prev = prev, row
    return prev[-1]


def brackets(text):
    pairs = {")": "(", "]": "[", "}": "{"}
    stack, quote, escape, comment = [], False, False, False
    for char in text:
        if comment:
            if char == "\n":
                comment = False
        elif quote:
            if escape:
                escape = False
            elif char == "\\":
                escape = True
            elif char == '"':
                quote = False
        elif char == '"':
            quote = True
        elif char == "#":
            comment = True
        elif char in "([{":
            stack.append(char)
        elif char in pairs:
            if not stack or stack.pop() != pairs[char]:
                return False
    return not quote and not escape and not stack


def schedule(n, prerequisites, priorities, durations):
    outgoing = [[] for _ in range(n)]
    indegree = [0] * n
    for a, b in prerequisites:
        outgoing[a].append(b)
        indegree[b] += 1
    ready = [(priorities[i], durations[i], i) for i in range(n) if not indegree[i]]
    heapq.heapify(ready)
    result = []
    while ready:
        _, _, node = heapq.heappop(ready)
        result.append(node)
        for after in outgoing[node]:
            indegree[after] -= 1
            if not indegree[after]:
                heapq.heappush(ready, (priorities[after], durations[after], after))
    return result if len(result) == n else None


def anagram(a, b):
    def key(text):
        text = unicodedata.normalize("NFKC", text).casefold()
        return Counter(c for c in text if not c.isspace() and unicodedata.category(c)[0] != "P")
    return key(a) == key(b)


def flatten(value):
    out, work = [], [iter([value])]
    while work:
        try:
            item = next(work[-1])
        except StopIteration:
            work.pop()
            continue
        if isinstance(item, (list, tuple)):
            work.append(iter(item))
        else:
            out.append(item)
    return out


def lfu(capacity, operations):
    if capacity <= 0:
        return [None for op in operations if op[0] == "get"]
    values, buckets, minimum, out = {}, defaultdict(OrderedDict), 0, []

    def touch(key, value):
        nonlocal minimum
        _, frequency = values[key]
        buckets[frequency].pop(key)
        if not buckets[frequency] and minimum == frequency:
            minimum += 1
        values[key] = value, frequency + 1
        buckets[frequency + 1][key] = None

    for op in operations:
        if op[0] == "get":
            if op[1] not in values:
                out.append(None)
            else:
                value = values[op[1]][0]
                out.append(value)
                touch(op[1], value)
        elif op[1] in values:
            touch(op[1], op[2])
        else:
            if len(values) >= capacity:
                key = next(iter(buckets[minimum]))
                buckets[minimum].pop(key)
                del values[key]
            values[op[1]] = op[2], 1
            buckets[1][op[1]] = None
            minimum = 1
    return out


def rotate(v, amount, width):
    if not v:
        return []
    amount %= len(v)
    v = v[-amount:] + v[:-amount] if amount else v[:]
    out = []
    for i in range(0, len(v), width):
        block = v[i:i + width]
        if len(block) == width:
            block.reverse()
        out.extend(block)
    return out


def merge(iv, gap):
    out = []
    for start, end in sorted((min(a, b), max(a, b)) for a, b in iv):
        if out and start <= out[-1][1] + gap:
            out[-1][1] = max(out[-1][1], end)
        else:
            out.append([start, end])
    return out


def window(v, limit):
    if limit <= 0:
        return 0
    counts, left, best = Counter(), 0, 0
    for right, value in enumerate(v):
        counts[value] += 1
        while len(counts) > limit:
            counts[v[left]] -= 1
            if not counts[v[left]]:
                del counts[v[left]]
            left += 1
        best = max(best, right - left + 1)
    return best


def coupon(n, edges, start, goal):
    graph = [[] for _ in range(n)]
    for a, b, cost in edges:
        graph[a].append((b, cost))
    inf, dist = 10**30, [[10**30, 10**30] for _ in range(n)]
    dist[start][0] = 0
    todo = [(0, start, 0)]
    while todo:
        cost, node, used = heapq.heappop(todo)
        if cost != dist[node][used]:
            continue
        for after, weight in graph[node]:
            if cost + weight < dist[after][used]:
                dist[after][used] = cost + weight
                heapq.heappush(todo, (cost + weight, after, used))
            if not used and cost < dist[after][1]:
                dist[after][1] = cost
                heapq.heappush(todo, (cost, after, 1))
    answer = min(dist[goal])
    return None if answer == inf else answer


REFS = [weighted, path, edit, brackets, schedule, anagram, flatten, lfu, rotate, merge]


WRONG = [
    [lambda iv: weighted(iv) if not iv else [sum(x[2] for x in iv), len(iv)],
     lambda iv: [max((x[2] for x in iv), default=0), 1 if iv else 0]],
    [lambda n, e, s, g, h, b: path(n, e, s, g, 10**9, b),
     lambda n, e, s, g, h, b: path(n, e, s, g, h, [])],
    [lambda a, b, i, d, r, s: edit(a, b, i, d, r, 10**9),
     lambda a, b, i, d, r, s: edit(a, b, 1, 1, 1, 1)],
    [lambda text: text.count("(") == text.count(")") and text.count("[") == text.count("]") and text.count("{") == text.count("}"),
     lambda text: brackets(text.replace("#", ""))],
    [lambda n, p, pri, dur: list(range(n)), lambda n, p, pri, dur: schedule(n, p, [0] * n, dur)],
    [lambda a, b: Counter(a.lower()) == Counter(b.lower()), lambda a, b: set(a.casefold()) == set(b.casefold())],
    [lambda v: [x for x in v if not isinstance(x, (list, tuple))],
     lambda v: [y for x in v for y in (x if isinstance(x, list) else [x])]],
    [lambda c, ops: lfu(c, ops) if c else [], lambda c, ops: lfu(c, [["get", op[1]] if op[0] == "put" else op for op in ops])],
    [lambda v, a, w: rotate(v, a, 10**9), lambda v, a, w: rotate(v, a, w) if a >= 0 else rotate(v, abs(a), w)],
    [lambda iv, g: merge(iv, 0), lambda iv, g: merge(iv, max(0, g - 1))],
]


def _all_sets():
    return {seed: generate(seed) for seed in SEEDS}


def _small(tests):
    return [test for test in tests if len(json.dumps(test["args"], ensure_ascii=False)) < 10000]


def _passes(fn, tests):
    for test in tests:
        try:
            if fn(*json.loads(json.dumps(test["args"], ensure_ascii=False))) != test["expected"]:
                return False
        except Exception:
            return False
    return True


def test_layout_and_reference_values():
    sets = _all_sets()
    for questions in sets.values():
        assert [q.qid for q in questions] == [f"code-{i:02d}" for i in range(1, 13)]
        assert all(len(q.meta["tests"]) == 10 for q in questions)
        for q, reference in zip(questions[:10], REFS):
            assert all(reference(*test["args"]) == test["expected"] for test in q.meta["tests"])
        assert all(test["expected"] == _bug_reference(q.meta["bug"], test["args"])
                   for q in questions[10:] for test in q.meta["tests"])


def _bug_reference(name, args):
    return window(*args) if name == "distinct_window_invariant" else coupon(*args)


def test_prompts_are_deterministic_unique_and_protocol_terminated():
    for seed in SEEDS:
        first, second = generate(seed), generate(seed)
        assert first == second
        assert len({q.prompt for q in first}) == 12
        assert all(q.prompt.endswith("slow machine.") for q in first)


def test_each_question_has_adversarial_large_case():
    for q in generate("c0"):
        largest = max(len(json.dumps(test["args"], ensure_ascii=False)) for test in q.meta["tests"])
        if q.meta["name"] == "edit_distance":
            # The 500x500 dynamic-programming case is deliberately bounded:
            # making both strings 20 KB would require billions of cells even
            # for a correct solution and would leave no sandbox margin.
            assert max(len(test["args"][0]) for test in q.meta["tests"]) >= 500
        else:
            assert largest > 20_000


def test_wrong_solutions_fail():
    questions = generate("c0")
    for question, wrongs in zip(questions[:10], WRONG):
        for wrong in wrongs:
            assert not _passes(wrong, _small(question.meta["tests"])), question.meta["name"]


def _run(source, tests, timeout=5):
    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "runner.py").write_text(_RUNNER)
        (root / "solution.py").write_text(source)
        (root / "tests.json").write_text(json.dumps(tests))
        try:
            return subprocess.run([sys.executable, str(root / "runner.py"), str(root / "solution.py"),
                                   str(root / "tests.json")], timeout=timeout,
                                  stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL).returncode == 0
        except subprocess.TimeoutExpired:
            return False


def test_reference_solutions_are_fast_and_bug_sources_fail():
    # These are executable references in the test suite, separate from the
    # generator's implementations.  The full 25-seed value check above covers
    # every generated case; this check exercises the sandbox protocol too.
    q = generate("c0")
    sources = [
        "from bisect import bisect_right\n" + "def solve(iv):\n    o=sorted((min(a,b),max(a,b),r) for a,b,r in iv); e=[x[1] for x in o]; d=[(0,0)]\n    for i,(s,_,r) in enumerate(o,1):\n        j=bisect_right(e,s,hi=i-1); t=(d[j][0]+r,d[j][1]+1); d.append(max((t,d[i-1]),key=lambda x:(x[0],-x[1])))\n    return list(d[-1])\n",
        "def solve(v,a,w):\n    a%=len(v) if v else 1; v=v[-a:]+v[:-a] if a else v[:]; o=[]\n    for i in range(0,len(v),w):\n        b=v[i:i+w]; o.extend(b[::-1] if len(b)==w else b)\n    return o\n",
    ]
    assert _run(sources[0], q[0].meta["tests"])
    assert _run(sources[1], q[8].meta["tests"])
    for question in q[10:]:
        assert not _run(_BUG_SOURCES[question.meta["bug"]], question.meta["tests"])


def test_bug_prompts_show_non_exposing_calls_and_hidden_counterexamples():
    questions = generate("c0")
    assert {q.meta["bug"] for q in questions[10:]} == set(_BUG_SOURCES)
    for q in questions[10:]:
        assert "```python\n" + _BUG_SOURCES[q.meta["bug"]] + "```" in q.prompt
        assert len(re.findall(r"^- `solve\(", q.prompt, flags=re.M)) == 2
        assert "wrong result" not in q.prompt.lower()
        # The displayed ordinary calls are not the hidden adversarial cases.
        assert any(test["expected"] != _bug_reference(q.meta["bug"], test["args"])
                   for test in q.meta["tests"]) is False

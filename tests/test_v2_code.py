"""v2 code questions: independent references, wrong-but-plausible solutions, bug-fix tasks."""

import itertools
import json
import re
import subprocess
import sys
from collections import Counter

import pytest

from llm_iq_monitor.questions.code import _BUG_SOURCES, generate
from llm_iq_monitor.sandbox import _RUNNER

SEEDS = [f"c{n}" for n in range(25)]


@pytest.fixture(scope="module")
def sets():
    return {seed: generate(seed) for seed in SEEDS}


def _first(sets):
    return sets[SEEDS[0]]


# Independent reference implementations (different algorithms from the generator).
def _ref_balanced(text):
    t = "".join(c for c in text if c in "()[]{}")
    stack = []
    for c in t:
        if c in "([{":
            stack.append(c)
        elif not stack or "([{".index(stack.pop()) != ")]}".index(c):
            return False
    return not stack


def _ref_flatten(value):
    out, stack = [], [value]
    work = [(value, 0)]
    while work:
        items, i = work.pop()
        if i < len(items):
            work.append((items, i + 1))
            if isinstance(items[i], list):
                work.append((items[i], 0))
            else:
                out.append(items[i])
    del stack
    return out


def _ref_is_prime(n):
    if n < 2:
        return False
    if n % 2 == 0:
        return n == 2
    d = 3
    while d * d <= n:
        if n % d == 0:
            return False
        d += 2
    return True


def _ref_merge(intervals):
    pts = sorted([min(a, b), max(a, b)] for a, b in intervals)
    out = []
    i = 0
    while i < len(pts):
        lo, hi = pts[i]
        j = i + 1
        while j < len(pts) and pts[j][0] <= hi:
            hi = max(hi, pts[j][1])
            j += 1
        out.append([lo, hi])
        i = j
    return out


REFS = {
    "index_filtered_sum": lambda v, k: 0 if k == 0 else sum(x for i, x in enumerate(v) if i % abs(k) == 0),
    "longest_run": lambda v: max((len(list(g)) for _, g in itertools.groupby(v)), default=0),
    "second_largest_distinct": lambda v: sorted(set(v))[-2] if len(set(v)) > 1 else None,
    "balanced_brackets": _ref_balanced,
    "run_length_encoding": lambda t: [[c, len(list(g))] for c, g in itertools.groupby(t)],
    "anagram": lambda a, b: sorted("".join(a.split()).casefold()) == sorted("".join(b.split()).casefold()),
    "flatten": _ref_flatten,
    "prime_count": lambda ns: sum(map(_ref_is_prime, ns)),
    "rotate": lambda v, k: [v[(i - k) % len(v)] for i in range(len(v))] if v else [],
    "merge_intervals": _ref_merge,
}

# Wrong but plausible implementations that small hidden tests must reject.
WRONG = {
    "index_filtered_sum": [lambda v, k: sum(v[::k]) if k else 0,          # negative k crashes / wrong
                           lambda v, k: sum(v[abs(k) - 1::abs(k)]) if k else 0,  # off by one
                           lambda v, k: sum(v[::abs(k)])],                # forgets k == 0
    "longest_run": [lambda v: max((len(list(g)) for _, g in itertools.groupby(v)), default=1),
                    lambda v: max((len(list(g)) for _, g in itertools.groupby([str(x).lower() for x in v])), default=0)],
    "second_largest_distinct": [lambda v: sorted(v)[-2] if len(v) > 1 else None,
                                lambda v: sorted(set(v))[-2] if len(set(v)) > 1 else 0 if not v else None],
    "balanced_brackets": [lambda t: t.count("(") == t.count(")") and t.count("[") == t.count("]") and t.count("{") == t.count("}")],
    "run_length_encoding": [lambda t: [[c, len(list(g))] for c, g in itertools.groupby(t.lower())],
                            lambda t: [(c, len(list(g))) for c, g in itertools.groupby(t)]],
    "anagram": [lambda a, b: sorted(a.replace(" ", "").lower()) == sorted(b.replace(" ", "").lower()),
                lambda a, b: set("".join(a.split()).casefold()) == set("".join(b.split()).casefold())],
    "flatten": [lambda v: [x for x in _ref_flatten(v) if x],
                lambda v: [y for x in v for y in (x if isinstance(x, list) else [x])]],
    "prime_count": [lambda ns: sum(1 for n in ns if abs(n) > 1 and _ref_is_prime(abs(n))),
                    lambda ns: sum(1 for n in ns if n > 2 and all(n % d for d in range(2, int(n ** .5))))],
    "rotate": [lambda v, k: v[k % len(v):] + v[:k % len(v)] if v else [],      # rotates left
               lambda v, k: v[-(k % len(v)) - 1:] + v[:-(k % len(v)) - 1] if v else [],  # off by one
               lambda v, k: v[-(abs(k) % len(v)):] + v[:-(abs(k) % len(v))] if v else []],  # ignores direction
    "merge_intervals": [lambda iv: _merge_strict(iv), lambda iv: _merge_unsorted(iv),
                        lambda iv: _ref_merge([[a, b] for a, b in iv if a <= b])],
}


def _merge_strict(intervals):
    out = []
    for a, b in sorted([min(x), max(x)] for x in intervals):
        if out and a < out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _merge_unsorted(intervals):
    out = []
    for a, b in intervals:
        if out and min(a, b) <= out[-1][1]:
            out[-1][1] = max(out[-1][1], a, b)
        else:
            out.append([min(a, b), max(a, b)])
    return out


def _small(tests):
    return [t for t in tests if len(json.dumps(t["args"])) < 5000]


def _passes(fn, tests):
    for test in tests:
        try:
            if fn(*json.loads(json.dumps(test["args"]))) != test["expected"]:
                return False
        except Exception:
            return False
    return True


def test_layout(sets):
    for qs in sets.values():
        assert [q.qid for q in qs] == [f"code-{i:02d}" for i in range(1, 13)]
        assert all(q.kind == "code" and len(q.meta["tests"]) == 10 for q in qs)
        assert all(q.meta["tests"] == json.loads(json.dumps(q.meta["tests"])) for q in qs[10:])


def test_hidden_tests_match_independent_references(sets):
    for qs in sets.values():
        for q in qs[:10]:
            reference = REFS[q.meta["name"]]
            for test in q.meta["tests"]:
                assert reference(*test["args"]) == test["expected"], q.meta["name"]


def test_each_function_has_a_large_case(sets):
    for q in _first(sets)[:10]:
        sizes = []
        for test in q.meta["tests"]:
            arg = test["args"][0]
            sizes.append(len(arg) if not isinstance(arg, list) else len(REFS["flatten"](arg)))
        assert max(sizes) >= 50_000, q.meta["name"]


def test_wrong_solutions_fail_on_small_tests(sets):
    for qs in sets.values():
        for q in qs[:10]:
            for index, wrong in enumerate(WRONG[q.meta["name"]]):
                assert not _passes(wrong, q.meta["tests"]), (q.meta["name"], index)


def test_tests_differ_between_seeds(sets):
    for index in range(12):
        assert len({json.dumps(sets[s][index].meta["tests"])[:20000] for s in SEEDS}) >= 20


def _run(source, tests, timeout):
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as directory:
        root = Path(directory)
        (root / "runner.py").write_text(_RUNNER)
        (root / "solution.py").write_text(source)
        (root / "tests.json").write_text(json.dumps(tests))
        try:
            return subprocess.run([sys.executable, str(root / "runner.py"), str(root / "solution.py"),
                                   str(root / "tests.json")], timeout=timeout, capture_output=True).returncode == 0
        except subprocess.TimeoutExpired:
            return False


GOOD = {
    "anagram": "from collections import Counter\n"
               "def solve(a, b):\n    f = lambda s: Counter(c for c in s.casefold() if not c.isspace())\n"
               "    return f(a) == f(b)\n",
    "rotate": "def solve(v, k):\n    if not v:\n        return []\n    k %= len(v)\n    return v[len(v) - k:] + v[:len(v) - k]\n",
    "balanced_brackets": "def solve(t):\n    p = {')': '(', ']': '[', '}': '{'}\n    s = []\n    for c in t:\n"
                         "        if c in '([{':\n            s.append(c)\n"
                         "        elif c in p and (not s or s.pop() != p[c]):\n            return False\n"
                         "    return not s\n",
}

QUADRATIC = {
    "anagram": "def solve(a, b):\n    a = [c for c in a.casefold() if not c.isspace()]\n"
               "    b = [c for c in b.casefold() if not c.isspace()]\n    for c in a:\n        if c in b:\n"
               "            b.remove(c)\n        else:\n            return False\n    return not b\n",
    "rotate": "def solve(v, k):\n    v = list(v)\n    if not v:\n        return v\n    for _ in range(k % len(v)):\n"
              "        v.insert(0, v.pop())\n    return v\n",
    "balanced_brackets": "def solve(t):\n    t = ''.join(c for c in t if c in '()[]{}')\n    while True:\n"
                         "        n = t.replace('()', '').replace('[]', '').replace('{}', '')\n"
                         "        if n == t:\n            return not t\n        t = n\n",
}


@pytest.mark.parametrize("name", sorted(GOOD))
def test_performance_case_separates_linear_from_quadratic(sets, name):
    # Sandbox limit is 10 s on 0.5 CPU; a correct solution is far below 2 s
    # here and the quadratic one exceeds 4 s even on a fast laptop.
    question = next(q for q in _first(sets) if q.meta["name"] == name)
    tests = question.meta["tests"]
    assert _run(GOOD[name], tests, timeout=5)
    assert not _run(QUADRATIC[name], tests, timeout=4)


def test_bug_prompts_show_code_and_failing_calls(sets):
    seen = set()
    for qs in sets.values():
        for q in qs[10:]:
            bug = q.meta["bug"]
            seen.add(bug)
            assert "```python\n" + _BUG_SOURCES[bug] + "```" in q.prompt
            shown = re.findall(r"^- `solve\(", q.prompt, flags=re.M)
            assert 1 <= len(shown) <= 3 and (bug == "mutable_default" or len(shown) >= 2)
            lowered = q.prompt.lower()
            for hint in ("off-by-one", "tie-break", "mutable", "float", "shadow", "inclusive", "integer division"):
                assert hint not in lowered
    assert seen == set(_BUG_SOURCES)


FIXED = {
    "inclusive_range": "def solve(a, b, d):\n    return 0 if a > b else b // d - (a - 1) // d\n",
    "mutable_default": "def solve(words, seen=None):\n    seen = set()\n    out = []\n    for w in words:\n"
                       "        if w.casefold() not in seen:\n            seen.add(w.casefold())\n            out.append(w)\n"
                       "    return out\n",
    "float_equality": "def solve(prices, target):\n    c = [round(p * 100) for p in prices]\n    t = round(target * 100)\n"
                      "    return sum(1 for i in range(len(c)) for j in range(i + 1, len(c)) if c[i] + c[j] == t)\n",
    "best_name": "def solve(scores):\n    if not scores:\n        return ''\n    top = max(p for _, p in scores)\n"
                 "    return min(n for n, p in scores if p == top)\n",
    "floor_median": "def solve(values):\n    v = sorted(values)\n    n = len(v)\n    if not n:\n        return None\n"
                    "    return v[n // 2] if n % 2 else (v[n // 2 - 1] + v[n // 2]) // 2\n",
    "shadowed_index": "def solve(groups):\n    return [(i + 1) * sum(g) for i, g in enumerate(groups)]\n",
}


def _exec(source):
    namespace = {}
    exec(source, namespace)  # noqa: S102 - test fixture code
    return namespace["solve"]


def _run_sequence(source, tests):
    """Run all tests in one module instance, like the sandbox runner."""
    solve = _exec(source)
    return all(solve(*json.loads(json.dumps(t["args"]))) == t["expected"] for t in tests)


def test_bug_fix_hidden_tests(sets):
    for qs in sets.values():
        for q in qs[10:]:
            bug = q.meta["bug"]
            tests = q.meta["tests"]
            assert _run_sequence(FIXED[bug], tests), bug
            assert not _run_sequence(_BUG_SOURCES[bug], tests), bug
            # Fixing only the shown calls (special-casing them) is not enough:
            # the hidden tests contain calls beyond the examples.
            shown = re.findall(r"^- `solve\((.*)\)` (?:should|followed)", q.prompt, flags=re.M)
            hidden_args = [repr(t["args"])[1:-1] for t in tests]
            assert any(args not in shown for args in hidden_args)


def test_bug_examples_are_true_statements(sets):
    for qs in sets.values():
        for q in qs[10:]:
            bug = q.meta["bug"]
            if bug == "mutable_default":
                continue
            fixed, buggy = _exec(FIXED[bug]), _exec(_BUG_SOURCES[bug])
            for call, expected, actual in re.findall(r"^- `solve\((.*)\)` should return `(.*)` but returns `(.*)`\.$",
                                                     q.prompt, flags=re.M):
                args = eval(f"[{call}]")  # noqa: S307 - generated test input
                assert repr(fixed(*args)) == expected
                assert repr(buggy(*args)) == actual != expected


def test_mutable_default_needs_independent_calls(sets):
    q = next(q for qs in sets.values() for q in qs[10:] if q.meta["bug"] == "mutable_default")
    stateful = ("_seen = set()\ndef solve(words):\n    out = []\n    for w in words:\n"
                "        if w.casefold() not in _seen:\n            _seen.add(w.casefold())\n            out.append(w)\n"
                "    return out\n")
    assert not _run_sequence(stateful, q.meta["tests"])
    assert Counter(type(t["args"][0]) for t in q.meta["tests"]) == {list: 10}

from llm_iq_monitor.questions import DIM_COUNTS, generate
import datetime as dt
import time


def _seeds(start, count):
    first = dt.date.fromisoformat(start[:4] + "-" + start[4:6] + "-" + start[6:])
    return [(first + dt.timedelta(days=i)).strftime("%Y%m%d") for i in range(count)]


def test_dimensions_have_documented_counts_and_are_deterministic():
    for dim, count in DIM_COUNTS.items():
        if dim == "code":
            continue
        first = generate(dim, "2026-11-02")
        second = generate(dim, "2026-11-02")
        assert len(first) == count
        assert first == second


def test_questions_change_with_seed():
    assert generate("math", "a") != generate("math", "b")


def test_all_but_k_birds_expected_is_k():
    from llm_iq_monitor.questions import generate

    for q in generate("trap", "20261102"):
        if "birds" in q.prompt:
            k = int(q.prompt.split("All but ")[1].split()[0])
            assert q.expected == k


def test_all_dimensions_generate_for_120_daily_seeds():
    dims = ("reasoning", "code", "instruction", "write_zh", "write_en", "ui", "trap", "math", "logic", "science")
    for seed in _seeds("20260101", 120):
        for dim in dims:
            questions = generate(dim, seed)
            assert len(questions) == DIM_COUNTS[dim]
            assert len({question.prompt for question in questions}) == len(questions)


def test_full_generation_is_fast():
    started = time.perf_counter()
    for dim in ("reasoning", "code", "instruction", "write_zh", "write_en", "ui", "trap", "math", "logic", "science"):
        generate(dim, "20260101")
    assert time.perf_counter() - started < 1.0


def test_ordering_facts_have_unique_linear_extension():
    # Independent brute force is intentionally limited to six names in this
    # test; the production generator uses a linear-time chain check.
    import itertools

    for question in generate("reasoning", "20260101"):
        if "order" not in question.meta:
            continue
        order = question.meta["order"][:6]
        facts = question.prompt.split("Facts: ", 1)[1].split(". Who is", 1)[0].split("; ")
        edges = []
        for fact in facts:
            if " is immediately before " in fact:
                edges.append(tuple(fact.split(" is immediately before ")))
            elif " is somewhere before " in fact:
                edges.append(tuple(fact.split(" is somewhere before ")))
        valid = []
        for candidate in itertools.permutations(order):
            positions = {name: candidate.index(name) for name in candidate}
            if all(left not in positions or right not in positions or positions[left] < positions[right] for left, right in edges):
                valid.append(candidate)
        assert len(valid) == 1

from llm_iq_monitor.questions import DIM_COUNTS, generate


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

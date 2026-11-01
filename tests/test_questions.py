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

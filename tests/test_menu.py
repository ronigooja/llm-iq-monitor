from llm_iq_monitor.menu import estimate_budget
from llm_iq_monitor.settings import Settings


def test_estimate_budget_scales_dimensions_and_efforts():
    settings = Settings()
    settings.models.per_model["demo"] = {
        "enabled": True,
        "interval_h": 6,
        "dims": ["math", "logic", "code"],
        "efforts": ["low", "high"],
    }
    budget = estimate_budget(settings)
    assert budget["runs_per_day"] == 8
    assert budget["input_tokens_per_day"] == 48000
    assert budget["output_tokens_per_day"] == 100000

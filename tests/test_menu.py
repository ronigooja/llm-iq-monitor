from datetime import datetime, timezone

from llm_iq_monitor.menu import (apply_model_choice, estimate_budget, next_heartbeat_ticks,
                                 set_enabled, validate_for_save)
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


def test_model_actions_respect_price_index_and_apply_choices():
    settings = Settings()
    set_enabled(settings, ["priced", "free"], True, {"priced": object()})
    assert settings.models.per_model["priced"].enabled
    assert "free" not in settings.models.per_model
    apply_model_choice(settings, ["priced"], 2, ["math"], ["medium"])
    assert settings.effective("priced").interval_h == 2


def test_ticks_and_save_validation_warnings():
    settings = Settings()
    settings.models.per_model["old"] = {"enabled": False, "interval_h": 1}
    settings.models.per_model["new"] = {"enabled": True, "interval_h": 1}
    settings.schedule.heartbeat_cron = "0 */2 * * *"
    warnings = validate_for_save(settings, ["new"], price_index={"new": object()})
    assert any("unknown model id: old" in warning for warning in warnings)
    assert any("interval shorter than heartbeat: new" in warning for warning in warnings)
    ticks = next_heartbeat_ticks("0 * * * *", now=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
    assert len(ticks) == 5
    assert ticks[0].hour == 1


def test_models_section_without_prices_does_not_open_empty_checkbox(monkeypatch):
    from llm_iq_monitor import menu

    monkeypatch.setattr(menu, "ensure_prices", lambda settings, output=print: {})
    asked, out = [], []

    class Ask:
        def __init__(self, value): self.value = value
        def ask(self): return self.value

    class Q:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                asked.append(name)
                if name == "select":
                    return Ask("2 Models" if asked.count("select") == 1 else "6 Quit")
                return Ask("" if name in ("text", "password") else False)
            return call

    async def fetch(settings): return ["m1"]

    menu.run_menu(menu.Settings(), q=Q(), output=out.append, model_fetcher=fetch, price_index={})
    assert "checkbox" not in asked
    assert any("No model has a price" in line for line in out)

from datetime import datetime, timezone

from llm_iq_monitor.admin_logic import (
    apply_model_choice,
    estimate_budget,
    next_heartbeat_ticks,
    set_enabled,
    validate_for_save,
    model_rows,
)
from llm_iq_monitor.settings import DIMS, LEGACY_DIMS, Settings


def test_estimate_budget_scales_dimensions_and_efforts():
    settings = Settings()
    settings.models.per_model["demo"] = {"enabled": True, "interval_h": 6, "dims": ["math", "logic", "code"], "efforts": ["low", "high"]}
    budget = estimate_budget(settings)
    assert budget["runs_per_day"] == 8
    assert budget["input_tokens_per_day"] == 46451
    assert budget["output_tokens_per_day"] == 92903
    assert budget["judge_calls_per_day"] == 0


def test_estimate_budget_counts_writing_judge_calls():
    settings = Settings()
    settings.models.per_model["writer"] = {"enabled": True, "interval_h": 24, "dims": ["write_zh", "write_en"], "efforts": ["low"]}
    budget = estimate_budget(settings)
    assert budget["runs_per_day"] == 1
    assert budget["judge_calls_per_day"] == 16
    assert budget["judge_input_tokens_per_day"] == 16000


def test_estimate_budget_uses_62_question_run_and_ui_questions():
    settings = Settings()
    settings.models.per_model["ui-model"] = {"enabled": True, "interval_h": 24, "dims": ["ui"], "efforts": ["low"]}
    budget = estimate_budget(settings)
    assert budget["input_tokens_per_day"] == 322
    assert budget["output_tokens_per_day"] == 645
    assert budget["output_tokens_with_thinking_per_day"] == 2580


def test_dimension_choices_exclude_legacy_dimensions():
    assert not set(LEGACY_DIMS) & set(DIMS)


def test_model_actions_respect_price_index_and_apply_choices():
    settings = Settings()
    set_enabled(settings, ["priced", "free"], True, {"priced": object()})
    assert settings.models.per_model["priced"].enabled
    assert "free" not in settings.models.per_model
    apply_model_choice(settings, ["priced"], 2, ["math"], ["medium"])
    assert settings.effective("priced").interval_h == 2


def test_model_rows_include_price_values_and_retain_priced_flag():
    rows = model_rows(Settings(), ["priced", "unpriced"], {"priced": ("provider", 1.25, 10.0)})
    assert rows == [
        {"id": "priced", "enabled": False, "interval_h": 6, "dims": list(DIMS), "efforts": ["medium"], "priced": True, "price_in": 1.25, "price_out": 10.0},
        {"id": "unpriced", "enabled": False, "interval_h": 6, "dims": list(DIMS), "efforts": ["medium"], "priced": False, "price_in": None, "price_out": None},
    ]


def test_ticks_and_save_validation_warnings():
    settings = Settings()
    settings.models.per_model["old"] = {"enabled": False, "interval_h": 1}
    settings.models.per_model["new"] = {"enabled": True, "interval_h": 1}
    settings.schedule.heartbeat_cron = "0 */2 * * *"
    warnings = validate_for_save(settings, ["new", "claude-opus-5-5"], price_index={"new": object(), "claude-opus-5-5": object()})
    assert any("unknown model id: old" in warning for warning in warnings)
    assert any("interval shorter than heartbeat: new" in warning for warning in warnings)
    ticks = next_heartbeat_ticks("0 * * * *", now=datetime(2026, 1, 1, 0, 1, tzinfo=timezone.utc))
    assert len(ticks) == 5
    assert ticks[0].hour == 1


def test_judge_validation_warns_when_absent_from_model_list():
    settings = Settings()
    warnings = validate_for_save(settings, [], price_index={"claude-opus-5-5": object()})
    assert any("judge model absent" in warning for warning in warnings)

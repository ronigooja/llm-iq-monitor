from pathlib import Path

import pytest

from llm_iq_monitor.settings import DIM_COUNTS, DIMS, Settings, load_settings, save_settings


def test_defaults_and_effective_model():
    settings = Settings()
    assert str(settings.gateway.models_url) == "https://ai.nodemgr.uk/v1/models"
    assert settings.effective("new").dims == list(DIMS)
    assert settings.effective("new").efforts == ["medium"]
    assert settings.models.default_dims is None
    assert settings.run.parallel_models == 1
    assert settings.run.max_attempts == 3
    assert settings.run.retry_delay_s == 10
    assert DIM_COUNTS == {"reasoning": 18, "code": 12, "instruction": 14, "write_zh": 8, "write_en": 8, "ui": 2,
                          "trap": 12, "math": 12, "logic": 12, "science": 12}
    assert settings.judge.model == "claude-opus-5-5"
    assert settings.judge.effort == "low"


def test_round_trip_uses_documented_model_table(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    settings = Settings()
    settings.models.per_model["demo-model"] = settings.effective("demo-model").model_copy(update={"enabled": True, "interval_h": 2})
    save_settings(settings)
    text = (tmp_path / "settings.toml").read_text()
    assert '[models.demo-model]' in text
    loaded = load_settings()
    assert loaded.models.per_model["demo-model"].interval_h == 2
    assert loaded.gateway.api_key is None


def test_legacy_six_dimension_default_list_loads_unchanged(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    (tmp_path / "settings.toml").write_text('''[models]\ndefault_dims = ["trap", "logic", "code", "instruction", "write_zh", "write_en"]\n\n[models.legacy]\ndims = ["math", "science", "code"]\n''')
    loaded = load_settings()
    assert loaded.models.default_dims == ["trap", "logic", "code", "instruction", "write_zh", "write_en"]
    assert loaded.effective("legacy").dims == ["math", "science", "code"]
    assert loaded.models.per_model["legacy"].dims == ["math", "science", "code"]


def test_default_dimensions_are_omitted_when_all_dimensions(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    save_settings(Settings())
    assert "default_dims" not in (tmp_path / "settings.toml").read_text()


def test_judge_effort_is_validated():
    with pytest.raises(ValueError):
        Settings(judge={"effort": "extreme"})


@pytest.mark.parametrize("value", [0, -1])
def test_ui_sample_max_age_is_at_least_one(value):
    with pytest.raises(ValueError):
        Settings(ui={"sample_max_age_days": value})


def test_parallel_models_is_bounded():
    with pytest.raises(ValueError):
        Settings(run={"parallel_models": 9})


def test_url_round_trip_serializes_as_strings():
    settings = Settings()
    dumped = settings.model_dump(mode="json")
    assert dumped["gateway"]["base_url"] == "https://ai.nodemgr.uk/v1"
    assert dumped["prices"]["url"] == "https://models.dev/api.json"

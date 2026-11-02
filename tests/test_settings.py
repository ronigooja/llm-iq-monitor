from pathlib import Path

from llm_iq_monitor.settings import DIM_COUNTS, DIMS, Settings, load_settings, save_settings


def test_defaults_and_effective_model():
    settings = Settings()
    assert str(settings.gateway.models_url) == "https://ai.nodemgr.uk/v1/models"
    assert settings.effective("new").dims == list(DIMS)
    assert settings.effective("new").efforts == ["medium"]
    assert settings.models.default_dims is None
    assert DIM_COUNTS == {"trap": 12, "math": 12, "logic": 12, "code": 10, "instruction": 12, "science": 12, "write_zh": 6, "write_en": 6}
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
    (tmp_path / "settings.toml").write_text('''[models]\ndefault_dims = ["trap", "math", "logic", "code", "instruction", "science"]\n''')
    loaded = load_settings()
    assert loaded.models.default_dims == ["trap", "math", "logic", "code", "instruction", "science"]
    assert loaded.effective("legacy").dims == loaded.models.default_dims


def test_default_dimensions_are_omitted_when_all_dimensions(monkeypatch, tmp_path: Path):
    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    save_settings(Settings())
    assert "default_dims" not in (tmp_path / "settings.toml").read_text()


def test_judge_effort_is_validated():
    import pytest
    with pytest.raises(ValueError):
        Settings(judge={"effort": "extreme"})


def test_url_round_trip_serializes_as_strings():
    settings = Settings()
    dumped = settings.model_dump(mode="json")
    assert dumped["gateway"]["base_url"] == "https://ai.nodemgr.uk/v1"
    assert dumped["prices"]["url"] == "https://models.dev/api.json"

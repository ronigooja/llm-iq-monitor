from pathlib import Path

from llm_iq_monitor.settings import DIMS, Settings, load_settings, save_settings


def test_defaults_and_effective_model():
    settings = Settings()
    assert str(settings.gateway.models_url) == "https://ai.nodemgr.uk/v1/models"
    assert settings.effective("new").dims == list(DIMS)
    assert settings.effective("new").efforts == ["medium"]


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

from datetime import datetime, timezone
import tomllib

from llm_iq_monitor.menu import (apply_model_choice, estimate_budget, next_heartbeat_ticks,
                                 set_enabled, validate_for_save)
from llm_iq_monitor.settings import DIMS, LEGACY_DIMS, Settings


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
    assert budget["input_tokens_per_day"] == 49655
    assert budget["output_tokens_per_day"] == 99310
    assert budget["judge_calls_per_day"] == 0


def test_estimate_budget_counts_writing_judge_calls():
    settings = Settings()
    settings.models.per_model["writer"] = {"enabled": True, "interval_h": 24, "dims": ["write_zh", "write_en"], "efforts": ["low"]}
    budget = estimate_budget(settings)
    assert budget["runs_per_day"] == 1
    assert budget["judge_calls_per_day"] == 12
    assert budget["judge_input_tokens_per_day"] == 12000


def test_estimate_budget_uses_58_question_run_and_ui_questions():
    settings = Settings()
    settings.models.per_model["ui-model"] = {
        "enabled": True, "interval_h": 24, "dims": ["ui"], "efforts": ["low"],
    }
    budget = estimate_budget(settings)
    assert budget["input_tokens_per_day"] == 344
    assert budget["output_tokens_per_day"] == 689
    assert budget["output_tokens_with_thinking_per_day"] == 2758
    assert budget["judge_calls_per_day"] == 0


def test_menu_dimension_choices_exclude_legacy_dimensions():
    from llm_iq_monitor import menu

    assert not set(LEGACY_DIMS) & set(menu.DIMS)
    assert set(menu.DIMS) == set(DIMS)


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


def test_judge_section_uses_priced_models_and_effort(monkeypatch):
    from llm_iq_monitor import menu
    asked = []

    class Ask:
        def __init__(self, value): self.value = value
        def ask(self): return self.value

    class Q:
        def __getattr__(self, name):
            def call(*args, **kwargs):
                asked.append((name, args, kwargs))
                if name == "select" and args[0] == "Configuration section": return Ask("5 Judge" if len([item for item in asked if item[0] == "select"]) == 1 else "7 Quit")
                if name == "select" and "Judge model" in args[0]: return Ask("priced-judge")
                if name == "select" and "Judge effort" in args[0]: return Ask("high")
                if name == "select": return Ask("7 Quit")
                return Ask(False)
            return call

    settings = Settings()
    menu.run_menu(settings, q=Q(), output=lambda _: None, model_fetcher=lambda _: [], price_index={"priced-judge": object()})
    assert settings.judge.model == "priced-judge"
    assert settings.judge.effort == "high"
    assert any("Judge model" in args[0] for name, args, _ in asked if name == "select")


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
                    return Ask("2 Models" if asked.count("select") == 1 else "7 Quit")
                return Ask("" if name in ("text", "password") else False)
            return call

    async def fetch(settings): return ["m1"]

    menu.run_menu(menu.Settings(), q=Q(), output=out.append, model_fetcher=fetch, price_index={})
    assert "checkbox" not in asked
    assert any("No model has a price" in line for line in out)


class _Answer:
    def __init__(self, value):
        self.value = value

    def ask(self):
        return self.value


class _SaveAndQuitQuestionary:
    def __init__(self):
        self.sections = 0

    def __getattr__(self, name):
        def call(*args, **kwargs):
            if name == "select" and args[0] == "Configuration section":
                self.sections += 1
                return _Answer("7 Quit")
            if name == "password":
                return _Answer("")
            if name == "confirm":
                return _Answer(args[0] == "Save settings and exit?")
            return _Answer(kwargs.get("default", ""))
        return call


def test_menu_loads_and_preserves_saved_settings(monkeypatch, tmp_path):
    from llm_iq_monitor import menu
    from llm_iq_monitor.settings import save_api_key, save_settings

    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    settings = Settings()
    settings.gateway.base_url = "https://gateway.example.test/custom"
    settings.gateway.models_url = "https://gateway.example.test/custom/models"
    settings.models.per_model["custom-model"] = {
        "enabled": True,
        "interval_h": 3,
        "dims": ["code", "write_en"],
        "efforts": ["low", "high"],
    }
    settings.judge.model = "custom-judge"
    settings.judge.effort = "high"
    save_settings(settings)
    save_api_key("test-key-123")

    menu.run_menu(None, q=_SaveAndQuitQuestionary(), output=lambda _: None,
                  model_fetcher=lambda _: ["custom-model", "custom-judge"],
                  price_index={"custom-model": object(), "custom-judge": object()})

    saved = tomllib.loads((tmp_path / "settings.toml").read_text())
    assert saved["gateway"]["base_url"] == "https://gateway.example.test/custom"
    assert saved["gateway"]["models_url"] == "https://gateway.example.test/custom/models"
    assert saved["models"]["custom-model"] == {
        "enabled": True,
        "interval_h": 3,
        "dims": ["code", "write_en"],
        "efforts": ["low", "high"],
    }
    assert saved["judge"] == {"model": "custom-judge", "effort": "high"}


def test_default_model_fetcher_uses_loaded_gateway_key(monkeypatch, tmp_path):
    from llm_iq_monitor import menu
    from llm_iq_monitor.settings import save_api_key, save_settings

    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    settings = Settings()
    settings.gateway.models_url = "https://gateway.example.test/models"
    save_settings(settings)
    save_api_key("test-key-123")
    seen = {}

    class Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return False

        async def get(self, url, *, headers):
            seen["url"] = url
            seen["headers"] = headers
            return Response()

    class Response:
        def raise_for_status(self):
            pass

        def json(self):
            return {"data": [{"id": "priced-model"}]}

    monkeypatch.setattr(menu.httpx, "AsyncClient", Client)

    class Q(_SaveAndQuitQuestionary):
        def __getattr__(self, name):
            def call(*args, **kwargs):
                if name == "select" and args[0] == "Configuration section":
                    self.sections += 1
                    return _Answer("2 Models" if self.sections == 1 else "7 Quit")
                if name == "checkbox":
                    return _Answer([])
                if name == "confirm":
                    return _Answer(False)
                return _Answer(kwargs.get("default", ""))
            return call

    menu.run_menu(None, q=Q(), output=lambda _: None, price_index={"priced-model": object()})
    assert seen == {
        "url": "https://gateway.example.test/models",
        "headers": {"Authorization": "Bearer test-key-123"},
    }


def test_menu_without_settings_starts_at_gateway(monkeypatch, tmp_path):
    from llm_iq_monitor import menu

    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(tmp_path))
    q = _SaveAndQuitQuestionary()
    menu.run_menu(None, q=q, output=lambda _: None, model_fetcher=lambda _: [],
                  price_index={"claude-opus-5-5": object()})
    assert q.sections == 1


def test_main_menu_loads_settings_before_starting(monkeypatch):
    from llm_iq_monitor import menu

    settings = Settings()
    loaded = []
    monkeypatch.setattr(menu, "load_settings", lambda: settings)
    monkeypatch.setattr(menu, "run_menu", lambda value: loaded.append(value))
    menu.main_menu()
    assert loaded == [settings]

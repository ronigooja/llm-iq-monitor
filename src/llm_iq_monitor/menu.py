"""Interactive configuration menu and testable menu helpers."""

from __future__ import annotations

import httpx
import questionary

from .settings import DIMS, EFFORTS, Settings, save_api_key, save_settings


def estimate_budget(settings: Settings) -> dict[str, float | int]:
    """Return the documented daily run and token estimate for enabled models."""
    runs = input_tokens = output_tokens = thinking_tokens = 0.0
    for model in settings.models.per_model:
        effective = settings.effective(model)
        if not effective.enabled:
            continue
        model_runs = 24 / effective.interval_h * len(effective.efforts)
        scale = len(effective.dims) / len(DIMS)
        runs += model_runs
        input_tokens += model_runs * 12000 * scale
        output_tokens += model_runs * 25000 * scale
        thinking_tokens += model_runs * 100000 * scale
    return {"runs_per_day": runs, "input_tokens_per_day": int(input_tokens),
            "output_tokens_per_day": int(output_tokens),
            "output_tokens_with_thinking_per_day": int(thinking_tokens)}


async def fetch_models(settings: Settings) -> list[str]:
    headers = {"Authorization": f"Bearer {settings.gateway.api_key.get_secret_value()}"} if settings.gateway.api_key else {}
    async with httpx.AsyncClient() as client:
        response = await client.get(str(settings.gateway.models_url), headers=headers)
        response.raise_for_status()
        payload = response.json()
    return [item["id"] for item in payload.get("data", []) if isinstance(item, dict) and "id" in item]


def _edit_settings(settings: Settings) -> Settings:
    # Keep this deliberately small: questionary handles SSH-friendly prompts and hidden passwords.
    settings.gateway.base_url = questionary.text("Base URL", default=str(settings.gateway.base_url)).ask()
    settings.gateway.models_url = questionary.text("Models URL", default=str(settings.gateway.models_url)).ask()
    key = questionary.password("Gateway key (leave blank to keep current)").ask()
    if key:
        save_api_key(key)
        settings.gateway.api_key = settings.gateway.api_key
    save_settings(settings)
    return settings


def run_menu(settings: Settings | None = None) -> Settings:
    return _edit_settings(settings or Settings())


def main_menu() -> None:
    run_menu()

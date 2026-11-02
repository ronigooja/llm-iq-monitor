"""Interactive configuration menu.

The state-changing helpers in this module are deliberately independent of
questionary, making the configuration workflow usable and testable without a
TTY (or a gateway).
"""
from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any, Callable

import httpx
import questionary
from apscheduler.triggers.cron import CronTrigger
from pydantic import SecretStr

from .db import connect
from .prices import load_price_index, refresh_prices
from .settings import DIM_COUNTS, DIMS, EFFORTS, LEGACY_DIMS, ModelSettings, Settings, save_api_key, save_settings


def estimate_budget(settings: Settings) -> dict[str, float | int]:
    total_questions = sum(DIM_COUNTS[dim] for dim in DIMS)
    runs = input_tokens = output_tokens = thinking_tokens = judge_calls = judge_input_tokens = judge_output_tokens = 0.0
    for model in settings.models.per_model:
        effective = settings.effective(model)
        if not effective.enabled:
            continue
        model_runs = 24 / effective.interval_h * len(effective.efforts)
        question_count = sum(DIM_COUNTS[dim] for dim in effective.dims)
        question_scale = question_count / total_questions
        writing_questions = sum(DIM_COUNTS[dim] for dim in effective.dims if dim in ("write_zh", "write_en"))
        runs += model_runs
        input_tokens += model_runs * 10000 * question_scale
        output_tokens += model_runs * 20000 * question_scale
        thinking_tokens += model_runs * min(80000 * question_scale, total_questions * settings.run.max_tokens)
        judge_calls += model_runs * writing_questions
        judge_input_tokens += model_runs * writing_questions * 1000
        judge_output_tokens += model_runs * writing_questions * 1000
    return {"runs_per_day": runs, "input_tokens_per_day": int(input_tokens),
            "output_tokens_per_day": int(output_tokens),
            "output_tokens_with_thinking_per_day": int(thinking_tokens),
            "judge_calls_per_day": int(judge_calls),
            "judge_input_tokens_per_day": int(judge_input_tokens),
            "judge_output_tokens_per_day": int(judge_output_tokens)}


def _menu_dims(settings: Settings, model_id: str | None = None) -> list[str]:
    configured = settings.models.default_dims
    if model_id is not None and model_id in settings.models.per_model:
        configured = settings.models.per_model[model_id]
    if isinstance(configured, ModelSettings):
        configured = configured.dims
    elif isinstance(configured, dict):
        configured = configured.get("dims")
    if model_id is not None and configured is None:
        configured = settings.effective(model_id).dims
    if configured is None:
        return list(DIMS)
    return [dim for dim in configured if dim in DIMS]


def _note_legacy_dims(settings: Settings, model_id: str | None, output: Callable[[str], None]) -> None:
    configured = settings.models.default_dims
    if model_id is not None and model_id in settings.models.per_model:
        configured = settings.models.per_model[model_id]
    if isinstance(configured, ModelSettings):
        configured = configured.dims
    elif isinstance(configured, dict):
        configured = configured.get("dims")
    if model_id is not None and configured is None:
        configured = settings.effective(model_id).dims
    legacy = [dim for dim in configured or [] if dim in LEGACY_DIMS]
    if legacy:
        output("Legacy dimensions are kept until changed: " + ", ".join(legacy))


async def fetch_models(settings: Settings) -> list[str]:
    headers = {"Authorization": f"Bearer {settings.gateway.api_key.get_secret_value()}"} if settings.gateway.api_key else {}
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.gateway.models_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    return [item["id"] for item in payload.get("data", []) if isinstance(item, dict) and "id" in item]


async def test_connection(settings: Settings) -> dict[str, Any]:
    """Test the models endpoint without including the secret in the result."""
    headers = {"Authorization": f"Bearer {settings.gateway.api_key.get_secret_value()}"} if settings.gateway.api_key else {}
    started = time.monotonic()
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.gateway.models_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    return {"status": response.status_code, "count": len(payload.get("data", [])),
            "elapsed_ms": int((time.monotonic() - started) * 1000)}


def next_heartbeat_ticks(cron: str, *, now: datetime | None = None, count: int = 5) -> list[datetime]:
    now = now or datetime.now(timezone.utc)
    trigger = CronTrigger.from_crontab(cron, timezone="UTC")
    result = []
    previous = now
    for _ in range(count):
        tick = trigger.get_next_fire_time(previous, previous)
        result.append(tick)
        previous = tick
    return result


def model_rows(settings: Settings, model_ids: list[str], price_index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    price_index = price_index if price_index is not None else load_price_index(connect())
    rows = []
    for model_id in model_ids:
        effective = settings.effective(model_id)
        rows.append({"id": model_id, "enabled": effective.enabled, "interval_h": effective.interval_h,
                     "dims": list(effective.dims), "efforts": list(effective.efforts),
                     "priced": model_id in price_index, "state": "enabled" if effective.enabled else "disabled"})
    return rows


def set_enabled(settings: Settings, model_ids: list[str], enabled: bool, price_index: dict[str, Any]) -> None:
    """Enable/disable models; unpriced models are never enable-able."""
    for model_id in model_ids:
        if enabled and model_id not in price_index:
            continue
        current = settings.models.per_model.get(model_id, ModelSettings())
        if isinstance(current, dict):
            current = ModelSettings.model_validate(current)
        settings.models.per_model[model_id] = current.model_copy(update={"enabled": enabled})


def edit_model(settings: Settings, model_id: str, interval_h: int, dims: list[str], efforts: list[str]) -> None:
    current = settings.models.per_model.get(model_id, ModelSettings())
    if isinstance(current, dict):
        current = ModelSettings.model_validate(current)
    settings.models.per_model[model_id] = current.model_copy(update={"interval_h": interval_h, "dims": dims, "efforts": efforts})


def apply_model_choice(settings: Settings, model_ids: list[str], interval_h: int, dims: list[str], efforts: list[str]) -> None:
    for model_id in model_ids:
        edit_model(settings, model_id, interval_h, dims, efforts)


def validate_for_save(settings: Settings, model_ids: list[str], *, price_index: dict[str, Any]) -> list[str]:
    for model_id, configured in list(settings.models.per_model.items()):
        if isinstance(configured, dict):
            settings.models.per_model[model_id] = ModelSettings.model_validate(configured)
    Settings.model_validate(settings)
    warnings = [f"unknown model id: {model_id}" for model_id in settings.models.per_model if model_id not in model_ids]
    if settings.judge.model not in price_index:
        raise ValueError(f"judge model without a price: {settings.judge.model}")
    if settings.judge.model not in model_ids:
        warnings.append(f"judge model absent from model list: {settings.judge.model}")
    # CronTrigger has no simple duration API; compare an interval to the first two ticks.
    ticks = next_heartbeat_ticks(settings.schedule.heartbeat_cron, count=2)
    period_h = (ticks[1] - ticks[0]).total_seconds() / 3600
    for model_id, configured in settings.models.per_model.items():
        if configured.enabled and model_id not in price_index:
            raise ValueError(f"model without a price cannot be enabled: {model_id}")
        interval = configured.interval_h or settings.models.default_interval_h
        if interval < period_h:
            warnings.append(f"interval shorter than heartbeat: {model_id}")
    return warnings


def ensure_prices(settings: Settings, output: Callable[[str], None] = print) -> dict[str, Any]:
    """Fetch the price list once when the cache is empty (the runner does it only at startup)."""
    conn = connect()
    try:
        asyncio.run(refresh_prices(conn, settings.prices.url))
    except Exception as exc:
        output(f"Price fetch failed: {exc}")
    return load_price_index(conn)


def _ask(q: Any, name: str, *args: Any, **kwargs: Any) -> Any:
    return getattr(q, name)(*args, **kwargs).ask()


def run_menu(settings: Settings | None = None, *, q: Any = questionary, output: Callable[[str], None] = print,
             model_fetcher: Callable[[Settings], Any] = fetch_models, price_index: dict[str, Any] | None = None) -> Settings:
    settings = settings or Settings()
    price_index = price_index if price_index is not None else load_price_index(connect())
    model_ids: list[str] = []
    section = 1
    first = True
    while True:
        choices = ["1 Gateway", "2 Models", "3 Defaults and heartbeat", "4 Run limits", "5 Judge", "6 Review", "7 Quit"]
        section = 1 if first else _ask(q, "select", "Configuration section", choices=choices, default=choices[section - 1])
        first = False
        section = int(str(section).split()[0])
        if section == 1:
            settings.gateway.base_url = _ask(q, "text", "Base URL", default=settings.gateway.base_url)
            settings.gateway.models_url = _ask(q, "text", "Models URL", default=settings.gateway.models_url)
            key = _ask(q, "password", "Gateway key (hidden; blank keeps current)")
            if key:
                save_api_key(key); settings.gateway.api_key = SecretStr(key)
            if _ask(q, "confirm", "Test connection now?", default=False):
                try: output(str(asyncio.run(test_connection(settings))))
                except Exception as exc: output(f"Connection failed: {exc}")
        elif section == 2:
            if not price_index:
                price_index = ensure_prices(settings, output)
            try: model_ids = asyncio.run(model_fetcher(settings))
            except Exception as exc: output(f"Model fetch failed: {exc}"); continue
            for row in model_rows(settings, model_ids, price_index): output(f"{row['id']}: {row['state']}, interval {row['interval_h']}h, dims={row['dims']}, efforts={row['efforts']}" + ("" if row["priced"] else " (no price)"))
            priced = [m for m in model_ids if m in price_index]
            if not priced:
                output("No model has a price yet. Check the price URL and network, then reopen this section.")
                continue
            checked = _ask(q, "checkbox", "Enable priced models", choices=priced)
            set_enabled(settings, checked, True, price_index)
            if checked and _ask(q, "confirm", "Edit one model?", default=False):
                model_id = _ask(q, "select", "Model", choices=checked)
                interval = int(_ask(q, "text", "Interval hours", default=str(settings.effective(model_id).interval_h)))
                _note_legacy_dims(settings, model_id, output)
                dims = _ask(q, "checkbox", "Dimensions", choices=list(DIMS), default=_menu_dims(settings, model_id))
                efforts = _ask(q, "checkbox", "Efforts", choices=list(EFFORTS), default=settings.effective(model_id).efforts)
                apply_model_choice(settings, checked if _ask(q, "confirm", "Apply to all checked?", default=False) else [model_id], interval, dims, efforts)
        elif section == 3:
            settings.schedule.heartbeat_cron = _ask(q, "text", "Heartbeat cron", default=settings.schedule.heartbeat_cron)
            output("Next five ticks: " + ", ".join(str(t) for t in next_heartbeat_ticks(settings.schedule.heartbeat_cron)))
            settings.models.default_interval_h = int(_ask(q, "text", "Default interval hours", default=str(settings.models.default_interval_h)))
            _note_legacy_dims(settings, None, output)
            settings.models.default_dims = _ask(q, "checkbox", "Default dimensions", choices=list(DIMS), default=_menu_dims(settings))
            settings.models.default_efforts = _ask(q, "checkbox", "Default efforts", choices=list(EFFORTS), default=settings.models.default_efforts)
            settings.prices.url = _ask(q, "text", "Price URL", default=settings.prices.url)
            settings.prices.refresh_cron = _ask(q, "text", "Price refresh cron", default=settings.prices.refresh_cron)
        elif section == 4:
            for obj, attr in ((settings.run, "parallel_models"), (settings.run, "timeout_s"), (settings.run, "max_tokens"), (settings.net, "rtt_fallback_ms"), (settings.retention, "reply_days"), (settings.ui, "sample_max_age_days")):
                setattr(obj, attr, int(_ask(q, "text", attr, default=str(getattr(obj, attr)))))
        elif section == 5:
            priced = list(price_index)
            if settings.judge.model not in price_index:
                output(f"Judge model has no price: {settings.judge.model}")
            if settings.judge.model not in model_ids:
                output(f"Judge model is absent from the current model list: {settings.judge.model}")
            if not priced:
                output("No priced models available for the judge.")
            else:
                settings.judge.model = _ask(q, "select", "Judge model (judge calls add cost)", choices=priced, default=settings.judge.model if settings.judge.model in priced else priced[0])
            settings.judge.effort = _ask(q, "select", "Judge effort (judge calls add cost)", choices=list(EFFORTS), default=settings.judge.effort)
        elif section == 6:
            output(str(settings.model_dump(mode="json", exclude={"gateway": {"api_key"}}, exclude_none=True)))
            output(str(estimate_budget(settings)))
            output("UI ratings need human time: about 2 samples per target per max-age window")
        else:
            if _ask(q, "confirm", "Save settings and exit?", default=True):
                validate_for_save(settings, model_ids, price_index=price_index); save_settings(settings)
            return settings


def main_menu() -> None:
    run_menu()

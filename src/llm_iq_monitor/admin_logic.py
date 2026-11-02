"""Configuration helpers shared by the web administrator and tests."""

from __future__ import annotations

import asyncio
import time
from datetime import datetime, timezone
from typing import Any

import httpx
from apscheduler.triggers.cron import CronTrigger

from .db import connect
from .discovery import sync_models
from .prices import load_price_index, refresh_prices
from .settings import DIM_COUNTS, DIMS, EFFORTS, LEGACY_DIMS, ModelSettings, Settings


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
    return {
        "runs_per_day": runs,
        "input_tokens_per_day": int(input_tokens),
        "output_tokens_per_day": int(output_tokens),
        "output_tokens_with_thinking_per_day": int(thinking_tokens),
        "judge_calls_per_day": int(judge_calls),
        "judge_input_tokens_per_day": int(judge_input_tokens),
        "judge_output_tokens_per_day": int(judge_output_tokens),
    }


def next_heartbeat_ticks(cron: str, *, now: datetime | None = None, count: int = 5) -> list[datetime]:
    now = now or datetime.now(timezone.utc)
    trigger = CronTrigger.from_crontab(cron, timezone="UTC")
    result: list[datetime] = []
    previous = now
    for _ in range(count):
        tick = trigger.get_next_fire_time(previous, previous)
        result.append(tick)
        previous = tick
    return result


def _as_model_settings(value: ModelSettings | dict[str, Any] | None) -> ModelSettings:
    if value is None:
        return ModelSettings()
    return value if isinstance(value, ModelSettings) else ModelSettings.model_validate(value)


def set_enabled(settings: Settings, model_ids: list[str], enabled: bool, price_index: dict[str, Any]) -> None:
    """Enable or disable models; a model without a cached price cannot be enabled."""
    for model_id in model_ids:
        if enabled and model_id not in price_index:
            continue
        current = _as_model_settings(settings.models.per_model.get(model_id))
        settings.models.per_model[model_id] = current.model_copy(update={"enabled": enabled})


def edit_model(settings: Settings, model_id: str, interval_h: int, dims: list[str], efforts: list[str]) -> None:
    current = _as_model_settings(settings.models.per_model.get(model_id))
    settings.models.per_model[model_id] = current.model_copy(update={"interval_h": interval_h, "dims": dims, "efforts": efforts})


def apply_model_choice(settings: Settings, model_ids: list[str], interval_h: int, dims: list[str], efforts: list[str]) -> None:
    for model_id in model_ids:
        edit_model(settings, model_id, interval_h, dims, efforts)


def validate_for_save(settings: Settings, model_ids: list[str], *, price_index: dict[str, Any]) -> list[str]:
    for model_id, configured in list(settings.models.per_model.items()):
        settings.models.per_model[model_id] = _as_model_settings(configured)
    Settings.model_validate(settings)
    warnings = [f"unknown model id: {model_id}" for model_id in settings.models.per_model if model_id not in model_ids]
    if settings.judge.model not in price_index:
        raise ValueError(f"judge model without a price: {settings.judge.model}")
    if settings.judge.model not in model_ids:
        warnings.append(f"judge model absent from model list: {settings.judge.model}")
    ticks = next_heartbeat_ticks(settings.schedule.heartbeat_cron, count=2)
    period_h = (ticks[1] - ticks[0]).total_seconds() / 3600
    for model_id, configured in settings.models.per_model.items():
        if configured.enabled and model_id not in price_index:
            raise ValueError(f"model without a price cannot be enabled: {model_id}")
        interval = configured.interval_h or settings.models.default_interval_h
        if interval < period_h:
            warnings.append(f"interval shorter than heartbeat: {model_id}")
    return warnings


async def fetch_models(settings: Settings) -> list[str]:
    key = settings.gateway.api_key.get_secret_value() if settings.gateway.api_key else None
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.gateway.models_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    return [item["id"] for item in payload.get("data", []) if isinstance(item, dict) and item.get("id")]


async def test_connection(settings: Settings) -> dict[str, Any]:
    """Test the gateway without putting the gateway secret in the result."""
    started = time.monotonic()
    key = settings.gateway.api_key.get_secret_value() if settings.gateway.api_key else None
    headers = {"Authorization": f"Bearer {key}"} if key else {}
    async with httpx.AsyncClient() as client:
        response = await client.get(settings.gateway.models_url, headers=headers)
        response.raise_for_status()
        payload = response.json()
    return {"status": response.status_code, "count": len(payload.get("data", [])), "elapsed_ms": int((time.monotonic() - started) * 1000)}


def model_rows(settings: Settings, model_ids: list[str], price_index: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    price_index = price_index if price_index is not None else load_price_index(connect())
    rows = []
    for model_id in model_ids:
        effective = settings.effective(model_id)
        rows.append({
            "id": model_id,
            "enabled": effective.enabled,
            "interval_h": effective.interval_h,
            "dims": list(effective.dims),
            "efforts": list(effective.efforts),
            "priced": model_id in price_index,
            "price_in": price_index[model_id][1] if model_id in price_index else None,
            "price_out": price_index[model_id][2] if model_id in price_index else None,
        })
    return rows


def ensure_prices(settings: Settings) -> dict[str, Any]:
    conn = connect()
    try:
        asyncio.run(refresh_prices(conn, settings.prices.url))
    except Exception:
        pass
    return load_price_index(conn)


__all__ = [
    "DIMS", "EFFORTS", "LEGACY_DIMS", "apply_model_choice", "edit_model", "ensure_prices",
    "estimate_budget", "fetch_models", "model_rows", "next_heartbeat_ticks", "set_enabled",
    "test_connection", "validate_for_save", "sync_models",
]

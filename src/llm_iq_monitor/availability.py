"""Availability probes, weighted aggregation, and busy/idle classification."""
from __future__ import annotations

import asyncio
import inspect
import logging
import math
import statistics
import time
from typing import Any, Callable


log = logging.getLogger(__name__)


def probe_interval(availability, state: str) -> int:
    """Return the probe interval in minutes for a classified state."""
    return (availability.probe_idle_every_min
            if state == "idle" else availability.probe_busy_every_min)


def weighted_ratio(probes: list[dict[str, Any]], start: float, end: float, cap: float) -> tuple[float | None, int]:
    """Return the time-weighted success ratio and sample count in a window."""
    selected = [p for p in probes if start <= p["t"] < end]
    if not selected:
        return None, 0
    selected.sort(key=lambda p: p["t"])
    total = good = 0.0
    for index, probe in enumerate(selected):
        nxt = selected[index + 1]["t"] if index + 1 < len(selected) else end
        weight = min(max(0.0, nxt - probe["t"]), cap)
        if weight:
            total += weight
            good += weight * bool(probe["ok"])
    return (good / total if total else None), len(selected)


def weighted_buckets(probes: list[dict[str, Any]], starts: list[float], width: float, cap: float) -> list[tuple[float | None, int]]:
    """Split each probe's coverage at bucket edges and aggregate each bucket."""
    result = []
    for start in starts:
        end = start + width
        total = good = 0.0
        count = sum(start <= p["t"] < end for p in probes)
        for index, probe in enumerate(sorted(probes, key=lambda p: p["t"])):
            nxt = sorted(probes, key=lambda p: p["t"])[index + 1]["t"] if index + 1 < len(probes) else end
            left, right = max(start, probe["t"]), min(end, probe["t"] + cap, nxt)
            if right > left:
                total += right - left
                good += (right - left) * bool(probe["ok"])
        result.append((good / total if total else None, count))
    return result


def classify(probes: list[dict[str, Any]], now: float, window_s: float, min_samples: int,
             fail_rate: float, latency_factor: float) -> str:
    recent = [p for p in probes if now - window_s <= p["t"] <= now]
    if len(recent) < min_samples:
        return "unknown"
    failures = sum(not p["ok"] for p in recent) / len(recent)
    successful = [p["latency_s"] for p in recent if p["ok"] and p.get("latency_s") is not None]
    baseline_values = [p["latency_s"] for p in probes if now - 7 * 86400 <= p["t"] <= now and p["ok"] and p.get("latency_s") is not None]
    latency_busy = False
    if successful and baseline_values:
        latency_busy = statistics.median(successful) >= latency_factor * sorted(baseline_values)[max(0, math.ceil(.2 * len(baseline_values)) - 1)]
    return "busy" if failures >= fail_rate or latency_busy else "idle"


async def probe_once(gateway, model: str, effort: str, timeout: float) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        reply = await gateway.chat(model, [{"role": "user", "content": "Reply with the single word: ok"}],
                                   effort=effort, max_tokens=64, timeout=timeout)
        text = getattr(reply, "reply", "")
        if not text or getattr(reply, "finish_reason", None) == "length":
            raise RuntimeError("empty or truncated reply")
        return {"ok": 1, "status": None, "latency_s": getattr(reply, "latency_s", None) or time.perf_counter() - started,
                "ttft_s": getattr(reply, "ttft_s", None), "error": None}
    except Exception as exc:
        return {"ok": 0, "status": getattr(exc, "status", None), "latency_s": time.perf_counter() - started,
                "ttft_s": None, "error": getattr(exc, "error", "network_error")}


async def probe_loop(settings, conn, gateway_factory: Callable, models_loader: Callable, stop_event: asyncio.Event):
    """Run probes independently of benchmark worker concurrency."""
    def current_settings():
        value = settings() if callable(settings) else settings
        return value

    log.info("probe loop started")
    while not stop_event.is_set():
        current = current_settings()
        if not current.availability.enabled:
            try:
                await asyncio.wait_for(stop_event.wait(), timeout=1)
            except asyncio.TimeoutError:
                pass
            continue
        try:
            models = await models_loader()
        except Exception:
            log.warning("probe model refresh failed", exc_info=True)
            models = []

        now = time.time()
        due = []
        smallest_interval = 30 * 60
        for model in models:
            try:
                effective = current.effective(model)
                if not effective.enabled:
                    continue
                state_row = conn.execute("SELECT state FROM probe_state WHERE model=? AND effort=?", (model, current.availability.probe_effort)).fetchone()
                state = state_row[0] if state_row else "unknown"
                interval = probe_interval(current.availability, state)
                smallest_interval = min(smallest_interval, interval * 60)
                last = conn.execute("SELECT MAX(t) FROM probes WHERE model=? AND effort=?", (model, current.availability.probe_effort)).fetchone()[0]
                if last is None or now - last >= interval * 60:
                    due.append(model)
            except Exception:
                log.warning("probe scheduling failed for model %s", model, exc_info=True)

        gateway = None
        if due:
            try:
                gateway = gateway_factory(current)
                if inspect.isawaitable(gateway):
                    gateway = await gateway
                for model in due:
                    try:
                        result = await probe_once(gateway, model, current.availability.probe_effort,
                                                  current.availability.probe_timeout_s)
                        timestamp = time.time()
                        conn.execute("INSERT INTO probes(model,effort,t,ok,status,latency_s,ttft_s,error) VALUES(?,?,?,?,?,?,?,?)",
                                     (model, current.availability.probe_effort, timestamp, result["ok"], result["status"],
                                      result["latency_s"], result["ttft_s"], result["error"]))
                        updated = conn.execute("SELECT MAX(updated_at) FROM probe_state WHERE model=? AND effort=?",
                                               (model, current.availability.probe_effort)).fetchone()[0]
                        if timestamp - (updated or 0) >= current.availability.classify_every_min * 60:
                            rows = [dict(row) for row in conn.execute(
                                "SELECT t,ok,latency_s FROM probes WHERE model=? AND effort=? AND t>=? ORDER BY t",
                                (model, current.availability.probe_effort, timestamp - 7 * 86400))]
                            new_state = classify(rows, timestamp, current.availability.state_window_min * 60,
                                                  current.availability.min_samples, current.availability.busy_fail_rate,
                                                  current.availability.busy_latency_factor)
                            old = conn.execute("SELECT state,since FROM probe_state WHERE model=? AND effort=?",
                                               (model, current.availability.probe_effort)).fetchone()
                            conn.execute("INSERT OR REPLACE INTO probe_state(model,effort,state,since,updated_at) VALUES(?,?,?,?,?)",
                                         (model, current.availability.probe_effort, new_state,
                                          old[1] if old and old[0] == new_state else timestamp, timestamp))
                    except Exception:
                        log.warning("probe failed for model %s", model, exc_info=True)
            except Exception:
                log.warning("probe gateway setup failed", exc_info=True)
            finally:
                close = getattr(gateway, "close", None)
                if close:
                    try:
                        value = close()
                        if inspect.isawaitable(value):
                            await value
                    except Exception:
                        log.warning("probe gateway close failed", exc_info=True)
        log.debug("probe cycle complete (%d due)", len(due))
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=min(30, smallest_interval))
        except asyncio.TimeoutError:
            pass

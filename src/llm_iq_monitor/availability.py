"""Availability probes, weighted aggregation, and busy/idle classification."""
from __future__ import annotations

import asyncio
import math
import statistics
import time
from typing import Any, Callable


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
    while not stop_event.is_set():
        if not settings.availability.enabled:
            await asyncio.sleep(1)
            continue
        models = await models_loader()
        now = time.time()
        for model in models:
            effective = settings.effective(model)
            if not effective.enabled:
                continue
            state_row = conn.execute("SELECT state FROM probe_state WHERE model=? AND effort=?", (model, settings.availability.probe_effort)).fetchone()
            state = state_row[0] if state_row else "unknown"
            interval = settings.availability.probe_busy_every_min if state == "busy" else settings.availability.probe_idle_every_min
            last = conn.execute("SELECT MAX(t) FROM probes WHERE model=? AND effort=?", (model, settings.availability.probe_effort)).fetchone()[0]
            if last is not None and now - last < interval * 60:
                continue
            result = await probe_once(gateway_factory(settings), model, settings.availability.probe_effort, settings.availability.probe_timeout_s)
            timestamp = time.time()
            conn.execute("INSERT INTO probes(model,effort,t,ok,status,latency_s,ttft_s,error) VALUES(?,?,?,?,?,?,?,?)",
                         (model, settings.availability.probe_effort, timestamp, result["ok"], result["status"], result["latency_s"], result["ttft_s"], result["error"]))
            if timestamp - (conn.execute("SELECT MAX(updated_at) FROM probe_state WHERE model=? AND effort=?", (model, settings.availability.probe_effort)).fetchone()[0] or 0) >= settings.availability.classify_every_min * 60:
                rows = [dict(row) for row in conn.execute("SELECT t,ok,latency_s FROM probes WHERE model=? AND effort=? AND t>=? ORDER BY t", (model, settings.availability.probe_effort, timestamp - 7 * 86400))]
                new_state = classify(rows, timestamp, settings.availability.state_window_min * 60, settings.availability.min_samples,
                                     settings.availability.busy_fail_rate, settings.availability.busy_latency_factor)
                old = conn.execute("SELECT state,since FROM probe_state WHERE model=? AND effort=?", (model, settings.availability.probe_effort)).fetchone()
                conn.execute("INSERT OR REPLACE INTO probe_state(model,effort,state,since,updated_at) VALUES(?,?,?,?,?)",
                             (model, settings.availability.probe_effort, new_state, old[1] if old and old[0] == new_state else timestamp, timestamp))
        try:
            await asyncio.wait_for(stop_event.wait(), timeout=60)
        except asyncio.TimeoutError:
            pass

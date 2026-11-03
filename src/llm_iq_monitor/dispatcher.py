"""Heartbeat due checking and bounded FIFO dispatch."""
from __future__ import annotations
import asyncio
import inspect
import time
import logging
from collections import deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable

log = logging.getLogger(__name__)


def _minute(t: float) -> float:
    # Ticks fire a few ms after the minute; compare whole minutes so the jitter cannot delay a run by a heartbeat.
    return t - t % 60


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


class Dispatcher:
    def __init__(self, settings, *, db=None, runner=None, clock: Callable[[], float] = time.time,
                 models_loader=None):
        self.settings, self.db, self.runner, self.clock = settings, db, runner, clock
        self.models_loader = models_loader
        self.queue = deque()
        self.active: set[str] = set()
        self.last_trigger: dict[str, float] = {}
        self.previous_trigger: dict[str, float | None] = {}
        self._workers: list[asyncio.Task] = []

    async def tick(self, tick_time: float | None = None, models: list[str] | None = None):
        tick = self.clock() if tick_time is None else tick_time
        names = await self._models() if models is None else models
        for model in names:
            effective = self.settings.effective(model)
            if not _get(effective, "enabled", False) or model in self.active or model in self.queue:
                continue
            if self.db:
                lookup = getattr(self.db, "lookup", None)
                if lookup is None:
                    try:
                        from .prices import lookup as price_lookup
                        lookup = lambda model: price_lookup(self.db, model)
                    except ImportError:
                        lookup = None
                if lookup is not None:
                    value = lookup(model)
                    if inspect.isawaitable(value):
                        value = await value
                    if not value:
                        continue
            previous = self.last_trigger.get(model)
            if previous is None and self.db:
                previous = await self._last_trigger(model)
            interval = float(_get(effective, "interval_h", 1)) * 3600
            if previous is not None and _minute(tick) - _minute(previous) < interval:
                continue
            self.last_trigger[model] = tick
            self.previous_trigger[model] = previous
            await self._set_trigger(model, tick)
            self.queue.append((model, tick, "schedule"))
        await self._ensure_workers()
        return list(self.queue)

    async def manual(self, models: list[str]):
        for model in models:
            if model not in self.active and not any(x[0] == model for x in self.queue):
                self.queue.append((model, self.clock(), "manual"))
        await self._ensure_workers()
        return await self.wait()

    async def wait(self):
        """Wait for all currently queued work to finish."""
        while self._workers:
            workers = list(self._workers)
            await asyncio.gather(*workers)
            self._workers = [worker for worker in self._workers if not worker.done()]

    async def _models(self):
        if self.models_loader is not None:
            value = self.models_loader()
            return await value if inspect.isawaitable(value) else value
        if hasattr(self.settings, "gateway"):
            import llm_iq_monitor.discovery as discovery
            value = discovery.list_models(self.settings.gateway.models_url, self.settings.gateway.api_key)
            return await value if inspect.isawaitable(value) else value
        return []

    async def _last_trigger(self, model):
        value = self.db.last_trigger(model) if hasattr(self.db, "last_trigger") else None
        return await value if inspect.isawaitable(value) else value

    async def _set_trigger(self, model, tick):
        if hasattr(self.db, "set_last_trigger"):
            value = self.db.set_last_trigger(model, tick)
            if inspect.isawaitable(value): await value

    async def _ensure_workers(self):
        self._workers = [worker for worker in self._workers if not worker.done()]
        limit = int(_get(self.settings.run, "parallel_models", 1))
        while len(self._workers) < limit:
            self._workers.append(asyncio.create_task(self._worker()))

    async def _worker(self):
        while self.queue:
            model, tick, trigger = self.queue.popleft()
            self.active.add(model)
            try:
                if self.runner:
                    previous = self.previous_trigger.pop(model, None)
                    result = self.runner(model, tick=tick, trigger=trigger)
                    if asyncio.iscoroutine(result):
                        result = await result
                    aborted = False
                    run_ids = result if isinstance(result, (list, tuple)) else []
                    if self.db and run_ids:
                        statuses = []
                        for run_id in run_ids:
                            status = getattr(self.db, "run_status", None)
                            if status is not None:
                                value = status(run_id)
                                if inspect.isawaitable(value):
                                    value = await value
                                statuses.append(value)
                            elif hasattr(self.db, "conn"):
                                row = self.db.conn.execute(
                                    "SELECT status FROM runs WHERE id=?", (run_id,)
                                ).fetchone()
                                if row:
                                    statuses.append(row[0])
                        aborted = "aborted" in statuses
                    if aborted and trigger == "schedule":
                        await self._set_trigger(model, previous)
                        self.last_trigger[model] = previous
                        log.info("run aborted for %s after an exhausted question", model)
            finally:
                self.active.discard(model)


async def dispatch(dispatcher, tick_time=None):
    return await dispatcher.tick(tick_time)

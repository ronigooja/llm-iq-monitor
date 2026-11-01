"""Heartbeat due checking and bounded FIFO dispatch."""
from __future__ import annotations
import asyncio
import inspect
import time
from collections import deque
from dataclasses import dataclass
from typing import Any, Awaitable, Callable


def _get(obj, name, default=None):
    return obj.get(name, default) if isinstance(obj, dict) else getattr(obj, name, default)


class Dispatcher:
    def __init__(self, settings, *, db=None, runner=None, clock: Callable[[], float] = time.time):
        self.settings, self.db, self.runner, self.clock = settings, db, runner, clock
        self.queue = deque()
        self.active: set[str] = set()
        self.last_trigger: dict[str, float] = {}
        self._workers: list[asyncio.Task] = []

    async def tick(self, tick_time: float | None = None, models: list[str] | None = None):
        tick = self.clock() if tick_time is None else tick_time
        names = models or await self._models()
        for model in names:
            effective = self.settings.effective(model)
            if not _get(effective, "enabled", False) or model in self.active or model in self.queue:
                continue
            if self.db and hasattr(self.db, "lookup") and not self.db.lookup(model):
                continue
            previous = self.last_trigger.get(model)
            if previous is None and self.db:
                previous = await self._last_trigger(model)
            interval = float(_get(effective, "interval_h", 1)) * 3600
            if previous is not None and tick - previous < interval:
                continue
            self.last_trigger[model] = tick
            await self._set_trigger(model, tick)
            self.queue.append((model, tick, "schedule"))
        await self._ensure_workers()
        return list(self.queue)

    async def manual(self, models: list[str]):
        for model in models:
            if model not in self.active and not any(x[0] == model for x in self.queue):
                self.queue.append((model, self.clock(), "manual"))
        await self._ensure_workers()

    async def _models(self):
        if hasattr(self.settings, "gateway"):
            import llm_iq_monitor.discovery as discovery
            return await discovery.list_models(self.settings.gateway.models_url, self.settings.gateway.api_key)
        return []

    async def _last_trigger(self, model):
        value = self.db.last_trigger(model) if hasattr(self.db, "last_trigger") else None
        return await value if inspect.isawaitable(value) else value

    async def _set_trigger(self, model, tick):
        if hasattr(self.db, "set_last_trigger"):
            value = self.db.set_last_trigger(model, tick)
            if inspect.isawaitable(value): await value

    async def _ensure_workers(self):
        limit = int(_get(self.settings.run, "parallel_models", 1))
        while len(self._workers) < limit:
            self._workers.append(asyncio.create_task(self._worker()))

    async def _worker(self):
        while self.queue:
            model, tick, trigger = self.queue.popleft()
            self.active.add(model)
            try:
                if self.runner:
                    result = self.runner(model, tick=tick, trigger=trigger)
                    if asyncio.iscoroutine(result): await result
            finally:
                self.active.discard(model)


async def dispatch(dispatcher, tick_time=None):
    return await dispatcher.tick(tick_time)

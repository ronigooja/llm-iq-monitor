import asyncio
from types import SimpleNamespace

import pytest

from llm_iq_monitor.dispatcher import Dispatcher


class Settings:
    run = SimpleNamespace(parallel_models=2)
    gateway = SimpleNamespace(models_url="http://models", api_key=None)
    def __init__(self, models): self.models = models
    def effective(self, model): return self.models.get(model, SimpleNamespace(enabled=False, interval_h=1))


class DB:
    def __init__(self, prices=None, last=None): self.prices, self.last, self.triggers = prices or set(), last or {}, []
    def lookup(self, model): return (1, 2, 3) if model in self.prices else None
    def last_trigger(self, model): return self.last.get(model)
    def set_last_trigger(self, model, tick): self.triggers.append((model, tick))


@pytest.mark.asyncio
async def test_due_uses_tick_time_and_skips_unpriced_absent_and_running(monkeypatch):
    settings = Settings({m: SimpleNamespace(enabled=True, interval_h=1) for m in ("good", "missing", "busy", "unpriced")})
    db = DB({"good", "busy"}, {"good": 0})
    seen = []
    d = Dispatcher(settings, db=db, runner=lambda model, **kw: seen.append(model), clock=lambda: 999)
    monkeypatch.setattr("llm_iq_monitor.discovery.list_models", lambda *a: ["good", "busy", "unpriced"])
    d.active.add("busy")
    await d.tick(3599)
    assert list(d.queue) == []
    await d.tick(3600)
    await asyncio.gather(*d._workers)
    assert seen == ["good"]
    assert db.triggers == [("good", 3600)]
    await d.tick(7200)
    await asyncio.gather(*d._workers)
    assert seen == ["good", "good"]


@pytest.mark.asyncio
async def test_fifo_parallel_limit_and_manual_trigger(monkeypatch):
    models = {m: SimpleNamespace(enabled=True, interval_h=1) for m in "abc"}
    settings = Settings(models)
    db = DB(set("abc"))
    active, order, maximum = 0, [], 0
    async def runner(model, **kwargs):
        nonlocal active, maximum
        active += 1; maximum = max(maximum, active); order.append(model)
        await asyncio.sleep(0)
        active -= 1
    d = Dispatcher(settings, db=db, runner=runner)
    monkeypatch.setattr("llm_iq_monitor.discovery.list_models", lambda *a: ["a", "b", "c"])
    await d.tick(1)
    await asyncio.gather(*d._workers)
    assert order == ["a", "b", "c"] and maximum <= 2


def test_efforts_are_normalized_in_documented_order():
    from llm_iq_monitor.runner import run_model
    assert run_model.__doc__

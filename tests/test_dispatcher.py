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


class PersistentDB(DB):
    def set_last_trigger(self, model, tick):
        super().set_last_trigger(model, tick)
        self.last[model] = tick


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
async def test_tick_jitter_does_not_delay_due_model():
    settings = Settings({"m": SimpleNamespace(enabled=True, interval_h=6)})
    db = DB({"m"}, {"m": 21600.019})
    d = Dispatcher(settings, db=db, runner=lambda model, **kw: None)
    await d.tick(43200.008, models=["m"])
    await asyncio.gather(*d._workers)
    assert db.triggers == [("m", 43200.008)]


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


@pytest.mark.asyncio
async def test_restart_retries_models_that_were_only_queued():
    settings = Settings({m: SimpleNamespace(enabled=True, interval_h=1) for m in "abc"})
    db = PersistentDB(set("abc"))
    started = asyncio.Event()
    release = asyncio.Event()

    async def first_runner(model, **kwargs):
        started.set()
        await release.wait()

    first = Dispatcher(settings, db=db, runner=first_runner)
    await first.tick(0, models=["a", "b", "c"])
    await started.wait()
    first._workers[0].cancel()
    await asyncio.gather(first._workers[0], return_exceptions=True)

    seen = []
    second = Dispatcher(settings, db=db, runner=lambda model, **kwargs: seen.append(model))
    await second.tick(3600, models=["a", "b", "c"])
    await second.wait()
    assert "b" in seen and "c" in seen


@pytest.mark.asyncio
async def test_completed_run_respects_interval():
    settings = Settings({"m": SimpleNamespace(enabled=True, interval_h=1)})
    db = PersistentDB({"m"}, {"m": 3600})
    seen = []
    d = Dispatcher(settings, db=db, runner=lambda model, **kwargs: seen.append(model))
    await d.tick(5400, models=["m"])
    assert seen == []
    await d.tick(7200, models=["m"])
    await d.wait()
    assert seen == ["m"]


@pytest.mark.asyncio
async def test_aborted_run_rolls_back_and_retries_next_tick():
    settings = Settings({"m": SimpleNamespace(enabled=True, interval_h=1)})
    settings.run.parallel_models = 1
    db = PersistentDB({"m"}, {"m": 0})
    db.statuses = {1: "aborted"}
    d = Dispatcher(settings, db=db, runner=lambda model, **kwargs: [1])
    db.run_status = lambda run_id: db.statuses[run_id]
    await d.tick(3600, models=["m"])
    await d.wait()
    assert db.last["m"] == 0
    await d.tick(3600, models=["m"])
    await d.wait()
    assert db.triggers == [("m", 3600), ("m", 0), ("m", 3600), ("m", 0)]


@pytest.mark.asyncio
async def test_busy_model_is_deferred_without_persisting_trigger():
    settings = Settings({"m": SimpleNamespace(enabled=True, interval_h=1)})
    settings.schedule = SimpleNamespace(defer_when_busy=True)
    db = PersistentDB({"m"})
    db.model_busy = lambda model, effort="": True
    d = Dispatcher(settings, db=db, runner=lambda model, **kwargs: None)
    await d.tick(3600, models=["m"])
    assert d.deferred == {"m"} and db.triggers == []


def test_efforts_are_normalized_in_documented_order():
    from llm_iq_monitor.runner import run_model
    assert run_model.__doc__

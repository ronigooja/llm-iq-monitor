import asyncio

import pytest

from llm_iq_monitor import db
from llm_iq_monitor import runner_main
from llm_iq_monitor.settings import Settings


def make_settings(cron="0 * * * *", interval=1):
    return Settings.model_validate({
        "gateway": {"base_url": "http://gateway.test/v1", "models_url": "http://gateway.test/v1/models"},
        "schedule": {"heartbeat_cron": cron},
        "models": {"demo": {"enabled": True, "interval_h": interval, "dims": ["math"], "efforts": ["low"]}},
    })


class FakeProbeGateway:
    instances = []
    failures = 0

    def __init__(self, *args, **kwargs):
        self.calls = 0
        self.closed = False
        type(self).instances.append(self)

    async def chat(self, model, messages, *, effort, max_tokens, timeout):
        self.calls += 1
        if type(self).failures:
            type(self).failures -= 1
            raise RuntimeError("probe failure")
        return type("Reply", (), {"reply": "ok", "finish_reason": "stop", "latency_s": 0.01,
                                   "ttft_s": 0.01})()

    async def close(self):
        self.closed = True


@pytest.mark.asyncio
async def test_async_main_heartbeat_persists_run_with_fake_gateway(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "monitor.db")
    conn.execute("INSERT INTO prices VALUES ('demo','openai',1,2,1)")
    stop = asyncio.Event()
    seen = []

    async def models(*args, **kwargs):
        return ["demo"]

    async def fake_run(model, **kwargs):
        seen.append(model)
        conn.execute("INSERT INTO runs(model,effort,seed,dataset_version,trigger,dims,params,status) VALUES (?,?,?,?,?,?,?,?)",
                     (model, "low", "seed", "v1", kwargs["trigger"], "[]", "{}", "ok"))

    monkeypatch.setattr("llm_iq_monitor.discovery.list_models", models)
    monkeypatch.setattr("llm_iq_monitor.runner.run_model", fake_run)

    class Scheduler:
        def __init__(self, heartbeat): self.heartbeat = heartbeat
        def start(self): asyncio.create_task(self.fire())
        async def fire(self):
            await self.heartbeat(100)
            await asyncio.sleep(0)
            stop.set()
        def shutdown(self, wait=False): pass

    monkeypatch.setattr("llm_iq_monitor.settings.watch_settings", lambda callback: asyncio.Future())
    await runner_main.main(settings=make_settings(), conn=conn, stop_event=stop,
                           scheduler_factory=lambda s, **kw: Scheduler(kw["heartbeat"]))
    assert seen == ["demo"]
    assert tuple(conn.execute("SELECT model,trigger FROM runs").fetchone()) == ("demo", "schedule")


@pytest.mark.asyncio
async def test_settings_reload_rebuilds_scheduler(monkeypatch, tmp_path):
    conn = db.connect(tmp_path / "monitor.db")
    conn.execute("INSERT INTO prices VALUES ('demo','openai',1,2,1)")
    stop = asyncio.Event()
    callbacks, schedulers = [], []

    async def models(*args, **kwargs): return ["demo"]
    async def watch(callback):
        callbacks.append(callback)
        await stop.wait()

    class Scheduler:
        def __init__(self): self.started = False
        def start(self): self.started = True
        def shutdown(self, wait=False): self.started = False

    def factory(*args, **kwargs):
        scheduler = Scheduler(); schedulers.append(scheduler); return scheduler

    monkeypatch.setattr("llm_iq_monitor.discovery.list_models", models)
    monkeypatch.setattr("llm_iq_monitor.settings.watch_settings", watch)
    def rebuild(old, settings, **kwargs):
        old.shutdown()
        new = factory(settings, **kwargs)
        new.start()
        return new
    monkeypatch.setattr("llm_iq_monitor.runner_main.rebuild_scheduler", rebuild)
    task = asyncio.create_task(runner_main.main(settings=make_settings(), conn=conn, stop_event=stop,
                                                scheduler_factory=factory))
    while not callbacks: await asyncio.sleep(0)
    await callbacks[0](make_settings(cron="*/5 * * * *", interval=2))
    assert len(schedulers) == 2 and schedulers[1].started
    stop.set()
    await task


@pytest.mark.asyncio
async def test_production_path_starts_probes_and_survives_probe_failure(monkeypatch, tmp_path):
    conn = db.connect(tmp_path / "monitor.db")
    stop = asyncio.Event()
    settings = make_settings()
    settings.availability.probe_idle_every_min = 1
    settings.availability.probe_timeout_s = 1
    settings.availability.classify_every_min = 1
    settings.availability.min_samples = 1
    settings.models.per_model["demo2"] = settings.models.per_model["demo"].model_copy()
    FakeProbeGateway.instances = []
    FakeProbeGateway.failures = 1
    probe_clock = [1_000_000.0]

    def fake_time():
        probe_clock[0] += 61
        return probe_clock[0]

    async def models(*args, **kwargs):
        return ["demo", "demo2"]

    class Scheduler:
        def start(self): pass
        def shutdown(self, wait=False): pass

    async def watch(callback):
        await stop.wait()

    monkeypatch.setattr("llm_iq_monitor.discovery.list_models", models)
    monkeypatch.setattr("llm_iq_monitor.settings.watch_settings", watch)
    monkeypatch.setattr("llm_iq_monitor.gateway.Gateway", FakeProbeGateway)
    monkeypatch.setattr("llm_iq_monitor.availability.time.time", fake_time)
    task = asyncio.create_task(runner_main._settings_main(
        settings=settings, conn=conn, stop_event=stop,
        scheduler_factory=lambda s, **kw: Scheduler()))
    for _ in range(100):
        if conn.execute("SELECT COUNT(*) FROM probes").fetchone()[0] >= 2:
            break
        await asyncio.sleep(0.01)
    stop.set()
    await task
    rows = conn.execute("SELECT ok FROM probes ORDER BY t").fetchall()
    assert [row[0] for row in rows] == [0, 1]
    assert FakeProbeGateway.instances and all(item.closed for item in FakeProbeGateway.instances)


@pytest.mark.asyncio
async def test_production_path_disabled_availability_writes_no_probes(monkeypatch, tmp_path):
    conn = db.connect(tmp_path / "monitor.db")
    stop = asyncio.Event()
    settings = make_settings()
    settings.availability.enabled = False

    async def models(*args, **kwargs):
        return ["demo"]

    class Scheduler:
        def start(self): pass
        def shutdown(self, wait=False): pass

    async def watch(callback):
        await stop.wait()

    monkeypatch.setattr("llm_iq_monitor.discovery.list_models", models)
    monkeypatch.setattr("llm_iq_monitor.settings.watch_settings", watch)
    monkeypatch.setattr("llm_iq_monitor.gateway.Gateway", FakeProbeGateway)
    task = asyncio.create_task(runner_main._settings_main(
        settings=settings, conn=conn, stop_event=stop,
        scheduler_factory=lambda s, **kw: Scheduler()))
    await asyncio.sleep(0.05)
    stop.set()
    await task
    assert conn.execute("SELECT COUNT(*) FROM probes").fetchone()[0] == 0


def test_manual_path_passes_tick_as_tick_time(monkeypatch):
    import asyncio
    from llm_iq_monitor import runner_main

    seen = {}

    async def fake_run_model(model, **kw):
        seen.update(kw)

    monkeypatch.setattr(runner_main.runner_module, "run_model", fake_run_model)
    from llm_iq_monitor.dispatcher import Dispatcher
    import inspect

    src = inspect.getsource(runner_main._manual_main)
    assert "tick_time=tick" in src

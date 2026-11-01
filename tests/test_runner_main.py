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

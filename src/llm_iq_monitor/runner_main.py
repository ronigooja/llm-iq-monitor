"""Runner process entry points.

The public ``serve`` and ``manual`` functions are deliberately synchronous so
they can be used by both argparse and ``python -m llm_iq_monitor``.
"""
from __future__ import annotations

import asyncio
import inspect
import logging
import signal
import sys
from pathlib import Path

from . import db as db_module
from . import discovery, prices, runner as runner_module
from .dispatcher import Dispatcher
from .scheduler import build_scheduler, rebuild_scheduler

log = logging.getLogger(__name__)


class DBAdapter:
    """Adapt the module-level SQLite functions to runner dependencies."""

    def __init__(self, conn):
        self.conn = conn

    def lookup(self, *args):
        model = args[-1]
        return prices.lookup(self.conn, model)

    def last_trigger(self, model):
        row = self.conn.execute("SELECT last_trigger_at FROM models WHERE id=?", (model,)).fetchone()
        return row[0] if row else None

    def set_last_trigger(self, model, tick):
        self.conn.execute("UPDATE models SET last_trigger_at=? WHERE id=?", (tick, model))

    def run_status(self, run_id):
        row = self.conn.execute("SELECT status FROM runs WHERE id=?", (run_id,)).fetchone()
        return row[0] if row else None

    def __getattr__(self, name):
        function = getattr(db_module, name)
        def call(*args, **kwargs):
            if args and args[0] is self.conn:
                args = args[1:]
            return function(self.conn, *args, **kwargs)
        return call


async def _call(value):
    return await value if inspect.isawaitable(value) else value


async def _settings_main(settings=None, *, conn=None, gateway_client=None, stop_event=None,
                         clock=None, scheduler_factory=build_scheduler, gateway_factory=None,
                         prices_client=None):
    from .settings import load_settings

    settings = settings or load_settings()
    owns_conn = conn is None
    conn = conn or db_module.connect()
    db_module.migrate(conn)
    db_module.mark_running_aborted(conn)
    adapter = DBAdapter(conn)
    gateway = settings.gateway

    async def fetch_models():
        return await discovery.list_models(gateway.models_url, gateway.api_key, client=gateway_client)

    model_list = await fetch_models()
    discovery.sync_models(conn, model_list)
    if conn.execute("SELECT 1 FROM prices LIMIT 1").fetchone() is None:
        await prices.refresh_prices(conn, settings.prices.url, client=prices_client)

    current_models = list(model_list)

    async def models_for_tick():
        nonlocal current_models
        current_models = await fetch_models()
        discovery.sync_models(conn, current_models)
        return current_models

    async def run_one(model, *, tick, trigger):
        kwargs = dict(settings=settings, conn=conn, db=adapter, tick_time=tick, trigger=trigger)
        if gateway_factory is not None:
            kwargs["gateway"] = gateway_factory(settings)
        return await runner_module.run_model(model, **kwargs)

    dispatcher = Dispatcher(settings, db=adapter, runner=run_one, clock=clock or __import__("time").time,
                            models_loader=models_for_tick)

    async def refresh():
        await prices.refresh_prices(conn, settings.prices.url, client=prices_client)

    async def maintenance():
        db_module.cleanup_replies(conn, settings.retention.reply_days)
        db_module.backup(conn, Path(__import__("os").environ.get("LLM_IQ_DATA_DIR", ".")) / "backups")

    scheduler = scheduler_factory(settings, heartbeat=dispatcher.tick, refresh_prices=refresh,
                                  maintenance=maintenance)
    scheduler.start()
    stop_event = stop_event or asyncio.Event()

    async def reload_settings(new_settings):
        nonlocal settings, scheduler
        old = settings
        dispatcher.settings = settings = new_settings
        if old.schedule.heartbeat_cron != new_settings.schedule.heartbeat_cron:
            scheduler = rebuild_scheduler(scheduler, new_settings, heartbeat=dispatcher.tick,
                                          refresh_prices=refresh, maintenance=maintenance)
        log.info("settings reloaded")

    async def watch():
        from .settings import watch_settings
        await watch_settings(reload_settings)

    watcher = asyncio.create_task(watch())
    try:
        await stop_event.wait()
    finally:
        watcher.cancel()
        await asyncio.gather(watcher, return_exceptions=True)
        await dispatcher.wait()
        scheduler.shutdown(wait=False)
        if owns_conn and conn is not None:
            conn.close()
    return dispatcher


async def _serve_main(**kwargs):
    stop = kwargs.pop("stop_event", None) or asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        try:
            loop.add_signal_handler(sig, stop.set)
        except (NotImplementedError, RuntimeError):
            signal.signal(sig, lambda *_: stop.set())
    return await _settings_main(stop_event=stop, **kwargs)


async def main(**kwargs):
    """Async service entry point, useful for embedding and tests."""
    return await _serve_main(**kwargs)


def serve(**kwargs):
    """Run the service until SIGTERM or SIGINT."""
    logging.basicConfig(level=logging.INFO, stream=sys.stdout,
                        format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    return asyncio.run(_serve_main(**kwargs))


async def _manual_main(models, *, settings=None, conn=None, dispatcher=None):
    owns_conn = conn is None
    if dispatcher is None:
        from .settings import load_settings
        settings = settings or load_settings()
        conn = conn or db_module.connect()
        db_module.migrate(conn)
        adapter = DBAdapter(conn)
        dispatcher = Dispatcher(
            settings, db=adapter,
            runner=lambda model, *, tick, trigger: runner_module.run_model(
                model, settings=settings, conn=conn, db=adapter, tick_time=tick, trigger=trigger),
        )
    await dispatcher.manual(list(models))
    for model in models:
        rows = dispatcher.db.conn.execute(
            "SELECT effort,status,id FROM runs WHERE model=? ORDER BY id", (model,)
        ).fetchall()
        for row in rows:
            dims = dispatcher.db.conn.execute(
                "SELECT dim,score FROM run_dims WHERE run_id=? ORDER BY dim", (row[2],)
            ).fetchall()
            cost = dispatcher.db.conn.execute("SELECT cost_usd FROM runs WHERE id=?", (row[2],)).fetchone()[0]
            print(f"{model} effort={row[0]} status={row[1]} "
                  f"scores={','.join(f'{d[0]}:{d[1]}' for d in dims)} cost={cost}")
    if owns_conn and conn is not None and dispatcher.db.conn is conn:
        conn.close()


def manual(models, **kwargs):
    """Run selected models once, without interval checks."""
    return asyncio.run(_manual_main(models, **kwargs))

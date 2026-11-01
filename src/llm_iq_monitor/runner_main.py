"""Runner process entry points."""
from __future__ import annotations
import asyncio


async def serve(*, settings=None, db=None, dispatcher=None, scheduler=None):
    if settings is None:
        from .settings import load_settings
        settings = load_settings()
    db = db or __import__("llm_iq_monitor.db", fromlist=["*"])
    conn = await _maybe(db.connect())
    await _maybe(db.migrate(conn))
    await _maybe(db.mark_running_aborted(conn))
    if scheduler: scheduler.start()
    try:
        await asyncio.Event().wait()
    finally:
        if scheduler: scheduler.shutdown(wait=False)


async def manual(models, *, settings=None, dispatcher=None):
    if settings is None:
        from .settings import load_settings
        settings = load_settings()
    if dispatcher is None:
        from .dispatcher import Dispatcher
        dispatcher = Dispatcher(settings)
    return await dispatcher.manual(list(models))


async def _maybe(value):
    import inspect
    return await value if inspect.isawaitable(value) else value

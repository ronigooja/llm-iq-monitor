"""APScheduler jobs for heartbeat, prices, and maintenance."""
from __future__ import annotations
from apscheduler.schedulers.asyncio import AsyncIOScheduler


def build_scheduler(settings, *, heartbeat, refresh_prices=None, maintenance=None, timezone="UTC"):
    scheduler = AsyncIOScheduler(timezone=timezone)
    opts = {"max_instances": 1, "coalesce": True, "misfire_grace_time": 900}
    scheduler.add_job(heartbeat, "cron", **_cron(settings.schedule.heartbeat_cron), id="heartbeat", **opts)
    if refresh_prices:
        scheduler.add_job(refresh_prices, "cron", **_cron(settings.prices.refresh_cron), id="prices", **opts)
    if maintenance:
        scheduler.add_job(maintenance, "cron", hour=4, minute=0, id="maintenance", **opts)
    return scheduler


def _cron(expression):
    fields = expression.split()
    if len(fields) != 5: raise ValueError("cron must have five fields")
    return dict(minute=fields[0], hour=fields[1], day=fields[2], month=fields[3], day_of_week=fields[4])


def rebuild_scheduler(old, settings, **kwargs):
    old.shutdown(wait=False)
    new = build_scheduler(settings, **kwargs)
    new.start()
    return new

import sqlite3
from pathlib import Path

import pytest
import yaml
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient

from llm_iq_monitor.db import connect

ROOT = Path(__file__).parents[1]


@pytest.fixture
async def history_client(tmp_path):
    path = tmp_path / "monitor.db"
    db = connect(path)
    db.execute("INSERT INTO models(id, active) VALUES ('m', 1)")
    db.execute("INSERT INTO availability_config VALUES (180, 3, 1)")
    now = 1700000000.0
    db.execute("INSERT INTO availability_runtime VALUES (?, ?, ?)", (now, 600, 1))
    # Unequal intervals and a failure stretch. The last sample also exercises
    # the capped partial current bucket.
    db.executemany(
        "INSERT INTO probes(model,effort,t,ok,status,latency_s,ttft_s,error) VALUES ('m','low',?,?,?,?,?,?)",
        [(now - 22 * 3600, 1, None, 100, None, None),
         (now - 18 * 3600, 0, None, 100, None, "failure"),
         (now - 12 * 3600, 0, None, 100, None, "failure"),
         (now - 6 * 3600, 1, None, 100, None, None),
         (now - 1800, 1, None, 100, None, None)],
    )
    db.commit()
    db.close()
    ds = Datasette([str(path)], metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()))
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as client:
        yield client, now


@pytest.mark.asyncio
async def test_history_is_aligned_and_includes_current_bucket(history_client):
    client, now = history_client
    response = await client.get("/monitor/availability_history.json", params={"model": "m", "effort": "low", "days": "1", "_shape": "array"})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 24
    current = int(now // 3600) * 3600
    assert [row["bucket_start"] for row in rows] == list(range(current - 23 * 3600, current + 3600, 3600))
    assert all(row["bucket_start"] % 3600 == 0 for row in rows)
    assert rows[-1]["bucket_start"] == current
    assert set(rows[-1]) == {"model", "effort", "bucket_start", "availability", "samples"}


@pytest.mark.asyncio
async def test_history_daily_count_alignment_and_time_weighting(history_client):
    client, now = history_client
    response = await client.get("/monitor/availability_history.json", params={"model": "m", "effort": "low", "days": "3", "_shape": "array"})
    assert response.status_code == 200, response.text
    rows = response.json()
    assert len(rows) == 3
    current_day = int(now // 86400) * 86400
    assert [row["bucket_start"] for row in rows] == [current_day - 2 * 86400, current_day - 86400, current_day]
    assert all(row["bucket_start"] % 86400 == 0 for row in rows)
    assert rows[-1]["samples"] >= 1
    # The day value is coverage-weighted, not an arithmetic mean of hourly values.
    hourly = await client.get("/monitor/availability_history.json", params={"model": "m", "effort": "low", "days": "1", "_shape": "array"})
    values = [row["availability"] for row in hourly.json() if row["availability"] is not None]
    assert rows[-1]["availability"] != sum(values) / len(values)

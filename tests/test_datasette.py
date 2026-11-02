from pathlib import Path

import pytest
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient
import yaml
from fixtures import monitor_db  # noqa: F401


ROOT = Path(__file__).parents[1]


@pytest.fixture
async def client(monitor_db):
    ds = Datasette(
        [str(monitor_db)],
        metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()),
        settings={"default_allow_sql": False, "allow_download": False, "default_cache_ttl": 60},
    )
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_canned_queries_and_exposure(client):
    expected = {
        "ranking": {"rank", "model", "effort", "run_id", "finished_at", "dataset_version", "status", "availability", "score", "quality", "latency_p50", "latency_p95", "ttft_p50", "time_total", "n", "n_err", "cost_usd", "cost_per_correct"},
        "series": {"t", "run_id", "dataset_version", "score", "quality", "latency_p50", "latency_p95", "ttft_p50", "time_total", "availability", "cost_per_correct"},
        "models": {"model", "effort", "active", "dims", "last_finished_at", "last_status"},
        "health": {"last_finished_at", "running_runs", "prices_fetched_at"},
    }
    params = {"ranking": {"dim": "math"}, "series": {"model": "alpha", "effort": "medium", "dim": "math"}, "models": {}, "health": {}}
    for name, columns in expected.items():
        response = await client.get(f"/monitor/{name}.json", params={**params[name], "_shape": "array"})
        assert response.status_code == 200, response.text
        assert set(response.json()[0]) == columns
    assert (await client.get("/monitor.json")).status_code == 403
    assert (await client.get("/monitor/runs.json")).status_code == 403
    assert (await client.get("/monitor.db")).status_code == 403


@pytest.mark.asyncio
async def test_quality_is_returned_but_does_not_change_ranking(client):
    ranking = await client.get("/monitor/ranking.json", params={"dim": "write_zh", "_shape": "array"})
    assert ranking.status_code == 200, ranking.text
    rows = ranking.json()
    assert [row["model"] for row in rows] == ["beta", "alpha"]
    assert [row["quality"] for row in rows] == [60, 78]

    series = await client.get("/monitor/series.json", params={"model": "alpha", "effort": "medium", "dim": "write_zh", "_shape": "array"})
    assert series.status_code == 200, series.text
    assert series.json()[0]["quality"] == 78

    null_quality = await client.get("/monitor/series.json", params={"model": "alpha", "effort": "medium", "dim": "write_en", "_shape": "array"})
    assert null_quality.json()[0]["quality"] is None

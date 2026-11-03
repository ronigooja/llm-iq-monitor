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
            "ranking": {"rank", "model", "effort", "run_id", "finished_at", "dataset_version", "status", "score", "quality", "latency_p50", "latency_p95", "ttft_p50", "time_total", "n", "n_err", "cost_usd", "cost_per_correct"},
        "best": {"dim", "use_when", "model", "effort"},
            "series": {"t", "run_id", "dataset_version", "score", "quality", "latency_p50", "latency_p95", "ttft_p50", "time_total", "cost_per_correct"},
        "models": {"model", "effort", "active", "dims", "last_finished_at", "last_status"},
        "health": {"last_finished_at", "running_runs", "prices_fetched_at", "dataset_version"},
    }
    params = {"ranking": {"dim": "math"}, "best": {}, "series": {"model": "alpha", "effort": "medium", "dim": "math"}, "models": {}, "health": {}}
    for name, columns in expected.items():
        response = await client.get(f"/monitor/{name}.json", params={**params[name], "_shape": "array"})
        assert response.status_code == 200, response.text
        assert set(response.json()[0]) == columns
    assert (await client.get("/monitor.json")).status_code == 403
    assert (await client.get("/monitor/runs.json")).status_code == 403
    assert (await client.get("/monitor.db")).status_code == 403


@pytest.mark.asyncio
async def test_ui_samples_has_expected_columns(client):
    response = await client.get("/monitor/ui_samples.json", params={"_shape": "array"})
    assert response.status_code == 200, response.text
    assert set(response.json()[0]) == {"sample_id", "model", "effort", "prompt_key", "prompt", "svg", "valid", "stars", "created_at"}


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


@pytest.mark.asyncio
async def test_public_views_follow_the_current_dataset_version(monitor_db):
    import sqlite3
    db = sqlite3.connect(monitor_db)
    db.execute("INSERT INTO runs VALUES (5,'beta','high','20261103','v3','schedule','[\"reasoning\"]','{}',1,2,120,200,210,'ok',10,0.1,2,NULL,NULL,NULL)")
    db.execute("INSERT INTO run_dims VALUES (5,'reasoning',70,18,0,2,3,1,24,100,50,0.1,0.01,NULL,NULL)")
    db.commit(); db.close()
    ds = Datasette([str(monitor_db)], metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()))
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as c:
        get = lambda name, **p: c.get(f"/monitor/{name}.json", params={**p, "_shape": "array"})
        assert (await get("health")).json()[0]["dataset_version"] == "v3"
        assert (await get("ranking", dim="math")).json() == []
        assert [r["model"] for r in (await get("ranking", dim="reasoning")).json()] == ["beta"]
        assert [(r["model"], r["dims"]) for r in (await get("models")).json()] == [("beta", "reasoning")]
        assert len((await get("series", model="alpha", effort="medium", dim="math")).json()) == 2

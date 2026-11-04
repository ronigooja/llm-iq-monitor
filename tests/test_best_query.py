import sqlite3
from pathlib import Path

import pytest
import yaml
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient

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


async def best(client, **params):
    response = await client.get("/monitor/best.json", params={**params, "_shape": "array"})
    assert response.status_code == 200, response.text
    return response.json()


def add_candidate_db(path):
    db = sqlite3.connect(path)
    db.executescript(
        """
        INSERT INTO models VALUES
          ('gamma-fast', 1, 1, 100, 100, 1),
          ('DELTA-cheap', 1, 1, 100, 100, 1),
          ('epsilon-null-price', 1, 1, 100, 100, 1),
          ('zeta-slow', 1, 1, 100, 100, 1);
        INSERT INTO runs VALUES
          (10,'gamma-fast','high','20261103','v1','schedule','["reasoning","code","ui"]','{}',1,2,120,90,110,'ok',10,0.1,2,NULL,NULL,NULL),
          (11,'DELTA-cheap','low','20261103','v1','schedule','["reasoning","code","ui"]','{}',1,2,120,90,111,'ok',10,0.1,2,NULL,NULL,NULL),
          (12,'epsilon-null-price','medium','20261103','v1','schedule','["reasoning"]','{}',1,2,120,90,112,'ok',10,0.1,2,NULL,NULL,NULL),
          (13,'zeta-slow','medium','20261103','v1','schedule','["reasoning"]','{}',1,2,120,90,113,'ok',10,0.1,2,NULL,NULL,NULL);
        INSERT INTO run_dims VALUES
          (10,'reasoning',100,12,0,8,9,1,24,100,50,0.2,0.20,NULL,NULL),
          (11,'reasoning',99,12,0,2,3,1,24,100,50,0.1,0.10,NULL,NULL),
          (12,'reasoning',99,12,0,1,2,1,24,100,50,0.1,NULL,NULL,NULL),
          (13,'reasoning',99,12,0,NULL,NULL,1,24,100,50,0.1,0.13,NULL,NULL),
          (10,'code',100,12,0,8,9,1,24,100,50,0.2,0.20,NULL,NULL),
          (11,'code',99,12,0,2,3,1,24,100,50,0.1,0.10,NULL,NULL),
          (10,'ui',50,2,0,8,9,1,24,100,50,0.2,0.20,NULL,NULL),
          (11,'ui',50,2,0,2,3,1,24,100,50,0.1,0.10,NULL,NULL);
        INSERT INTO ui_samples VALUES
          (10,10,'classic','pelican','<svg/>',1,10,300,110),
          (11,11,'classic','pelican','<svg/>',1,9,300,111);
        INSERT INTO runs VALUES
          (14,'gamma-fast','low','20261102','v0','schedule','["reasoning"]','{}',1,2,120,80,90,'ok',10,0.1,2,NULL,NULL,NULL);
        INSERT INTO run_dims VALUES (14,'reasoning',1,12,0,1,2,1,24,100,50,0.01,0.01,NULL,NULL);
        """
    )
    db.commit()
    db.close()


@pytest.mark.asyncio
async def test_best_selection_and_exact_public_columns(client, monitor_db):
    add_candidate_db(monitor_db)
    rows = await best(client)
    assert len(rows) == 6
    assert all(set(row) == {"dim", "use_when", "model", "effort"} for row in rows)
    assert not set().union(*(set(row) for row in rows)) & {
        "score", "cost_per_correct", "latency_p50", "availability", "run_id", "finished_at",
        "dataset_version", "input_usd_per_m", "output_usd_per_m",
    }
    by_dim = {row["dim"]: row for row in rows}
    assert by_dim["reasoning"]["model"] == "gamma-fast"
    assert by_dim["reasoning"]["effort"] == "high"
    assert by_dim["code"]["model"] == "gamma-fast"
    assert by_dim["ui"]["model"] == "gamma-fast"
    assert [row["dim"] for row in rows] == ["reasoning", "code", "instruction", "write_zh", "write_en", "ui"]
    assert by_dim["instruction"]["model"] is None
    assert by_dim["instruction"]["effort"] is None


@pytest.mark.asyncio
async def test_best_tolerances_price_latency_exclude_and_all_efforts(client, monitor_db):
    add_candidate_db(monitor_db)
    assert (await best(client, score_tolerance="1"))[0]["model"] == "DELTA-cheap"
    assert (await best(client, score_tolerance="1", price_tolerance="30"))[0]["model"] == "DELTA-cheap"
    assert (await best(client, score_tolerance="1", price_tolerance="31"))[0]["model"] == "DELTA-cheap"
    assert (await best(client, score_tolerance="1", exclude=" GAMMA , delta "))[0]["model"] == "zeta-slow"
    assert (await best(client, score_tolerance="1", exclude="gamma, delta", price_tolerance="0"))[0]["effort"] == "medium"
    excluded = await best(client, exclude="alpha, beta, gamma, delta, epsilon, zeta")
    assert len(excluded) == 6
    assert all(row["model"] is None and row["effort"] is None for row in excluded)


@pytest.mark.asyncio
async def test_best_empty_and_invalid_numeric_params_use_defaults(client, monitor_db):
    add_candidate_db(monitor_db)
    default = await best(client)
    empty = await best(client, score_tolerance="", price_tolerance="", exclude="")
    invalid = await best(client, score_tolerance="not-a-number", price_tolerance="nope")
    assert empty == default == invalid


@pytest.mark.asyncio
async def test_best_per_dimension_exclusions_are_local_and_combine_with_global(client, monitor_db):
    add_candidate_db(monitor_db)

    rows = {row["dim"]: row for row in await best(client, exclude_reasoning="GAMMA")}
    assert rows["reasoning"]["model"] == "DELTA-cheap"
    assert rows["code"]["model"] == "gamma-fast"

    rows = {row["dim"]: row for row in await best(client, exclude_code=" gamma , DELTA ")}
    assert rows["reasoning"]["model"] == "gamma-fast"
    assert rows["code"]["model"] is None
    assert rows["code"]["effort"] is None

    rows = {row["dim"]: row for row in await best(client, exclude="gamma", exclude_code=" DELTA ")}
    assert rows["reasoning"]["model"] == "DELTA-cheap"
    assert rows["code"]["model"] is None
    assert rows["ui"]["model"] == "DELTA-cheap"


@pytest.mark.asyncio
async def test_best_per_dimension_exclusions_ignore_empty_pieces(client, monitor_db):
    add_candidate_db(monitor_db)
    default = await best(client)
    excluded = await best(client, exclude_ui=" ,  ", exclude_reasoning=" , , ")
    assert excluded == default


@pytest.mark.asyncio
async def test_best_candidates_match_ranking_for_each_dimension(client, monitor_db):
    add_candidate_db(monitor_db)
    best_rows = {row["dim"]: row for row in await best(client, score_tolerance="0", price_tolerance="100000")}
    for dim in ("reasoning", "code", "ui"):
        ranking = await client.get("/monitor/ranking.json", params={"dim": dim, "_shape": "array"})
        assert ranking.status_code == 200, ranking.text
        models = {(row["model"], row["effort"]) for row in ranking.json() if row["score"] is not None}
        assert (best_rows[dim]["model"], best_rows[dim]["effort"]) in models


@pytest.mark.asyncio
async def test_disabled_model_is_hidden_and_reappears_when_enabled(client, monitor_db):
    add_candidate_db(monitor_db)
    db = sqlite3.connect(monitor_db)
    db.execute("UPDATE models SET enabled=0 WHERE id='gamma-fast'")
    db.commit()
    db.close()

    ranking = await client.get("/monitor/ranking.json", params={"dim": "reasoning", "_shape": "array"})
    assert ranking.status_code == 200
    assert "gamma-fast" not in {row["model"] for row in ranking.json()}
    models = await client.get("/monitor/models.json", params={"_shape": "array"})
    assert models.status_code == 200
    assert "gamma-fast" not in {row["model"] for row in models.json()}
    rows = await best(client)
    assert "gamma-fast" not in {row["model"] for row in rows}
    db = sqlite3.connect(monitor_db)
    assert db.execute("SELECT COUNT(*) FROM runs WHERE model='gamma-fast'").fetchone()[0] > 0
    db.execute("UPDATE models SET enabled=1 WHERE id='gamma-fast'")
    db.commit()
    db.close()
    ranking = await client.get("/monitor/ranking.json", params={"dim": "reasoning", "_shape": "array"})
    assert "gamma-fast" in {row["model"] for row in ranking.json()}
    assert any(row["model"] == "gamma-fast" for row in await best(client))


@pytest.mark.asyncio
async def test_best_ui_price_step_uses_total_cost(client, monitor_db):
    add_candidate_db(monitor_db)
    db = sqlite3.connect(monitor_db)
    db.execute("UPDATE ui_samples SET stars=10")
    # gamma-fast is faster (latency 1) but expensive; DELTA-cheap is slower (latency 5) but cheap.
    db.execute("UPDATE run_dims SET latency_p50=1, cost_usd=0.30 WHERE run_id=10 AND dim='ui'")
    db.execute("UPDATE run_dims SET latency_p50=5, cost_usd=0.10 WHERE run_id=11 AND dim='ui'")
    db.commit()
    db.close()
    by_dim = {row["dim"]: row for row in await best(client, price_tolerance="0")}
    assert by_dim["ui"]["model"] == "DELTA-cheap"
    by_dim = {row["dim"]: row for row in await best(client, price_tolerance="500")}
    assert by_dim["ui"]["model"] == "gamma-fast"

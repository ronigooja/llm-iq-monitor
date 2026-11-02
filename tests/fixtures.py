import sqlite3

import pytest


@pytest.fixture
def monitor_db(tmp_path):
    path = tmp_path / "monitor.db"
    db = sqlite3.connect(path)
    db.executescript(
        """
        CREATE TABLE models(id TEXT PRIMARY KEY, active INTEGER NOT NULL, first_seen REAL, last_seen REAL, last_trigger_at REAL);
        CREATE TABLE prices(model TEXT PRIMARY KEY, provider TEXT NOT NULL, input_usd_per_m REAL NOT NULL, output_usd_per_m REAL NOT NULL, fetched_at REAL NOT NULL);
        CREATE TABLE meta(key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE runs(id INTEGER PRIMARY KEY, model TEXT NOT NULL, effort TEXT NOT NULL, seed TEXT NOT NULL, dataset_version TEXT NOT NULL, trigger TEXT NOT NULL, dims TEXT NOT NULL, params TEXT NOT NULL, price_in REAL, price_out REAL, price_fetched_at REAL, started_at REAL, finished_at REAL, status TEXT NOT NULL, availability REAL, duration_s REAL, cost_usd REAL, rtt_ms REAL, judge_model TEXT, judge_price_in REAL, judge_price_out REAL);
        CREATE TABLE run_dims(run_id INTEGER NOT NULL, dim TEXT NOT NULL, score REAL, n INTEGER, n_err INTEGER, availability REAL, latency_p50 REAL, latency_p95 REAL, ttft_p50 REAL, time_total REAL, in_tok INTEGER, out_tok INTEGER, cost_usd REAL, cost_per_correct REAL, quality REAL, judge_cost_usd REAL, PRIMARY KEY(run_id, dim));
        CREATE TABLE results(id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL, qid TEXT NOT NULL, dim TEXT NOT NULL, correct INTEGER, error TEXT, finish_reason TEXT, latency_s REAL, ttft_s REAL, reasoning_ttft_s REAL, in_tok INTEGER, out_tok INTEGER, reasoning_tok INTEGER, quality REAL, judge_in_tok INTEGER, judge_out_tok INTEGER, judge_latency_s REAL, reply TEXT);
        INSERT INTO models VALUES ('alpha', 1, 1, 100, 100), ('beta', 1, 1, 100, 100);
        INSERT INTO prices VALUES ('alpha', 'openai', 1, 2, 120);
        INSERT INTO runs VALUES (1,'alpha','medium','20261102','v1','schedule','["math","logic","write_zh","write_en"]','{}',1,2,120,90,100,'ok',1,10,0.1,2,NULL,NULL,NULL);
        INSERT INTO runs VALUES (2,'beta','low','20261102','v1','schedule','["math","write_zh"]','{}',1,2,120,90,101,'partial',0.9,11,0.2,2,NULL,NULL,NULL);
        INSERT INTO runs VALUES (3,'alpha','medium','20261101','v0','schedule','["math"]','{}',1,2,120,80,89,'ok',1,9,0.1,2,NULL,NULL,NULL);
        INSERT INTO runs VALUES (4,'alpha','high','20261102','v1','schedule','["math"]','{}',1,2,120,90,102,'running',NULL,NULL,NULL,2,NULL,NULL,NULL);
        INSERT INTO run_dims VALUES (1,'math',90,12,0,1,2,3,1,24,100,50,0.1,0.01,NULL,NULL), (1,'logic',80,12,1,0.916,3,4,1.5,30,100,50,0.1,0.0125,NULL,NULL), (1,'write_zh',83.3,6,0,1,14,16,2,84,100,50,0.012,0.012,78,0.003), (1,'write_en',81,6,1,0.833,15,18,2.5,90,100,50,0.014,0.017,NULL,0.004), (2,'math',70,12,2,0.833,5,7,2,40,100,50,0.2,0.02,NULL,NULL), (2,'write_zh',95,6,0,1,10,12,1.5,60,100,50,0.01,0.01,60,0.002), (3,'math',85,12,0,1,2.5,3.5,1.2,25,100,50,0.1,0.011,NULL,NULL);
        INSERT INTO results VALUES (1,1,'write-zh-1','write_zh',1,NULL,'stop',14,2,1,100,50,10,78,20,30,0.2,'reply'), (2,1,'write-en-1','write_en',0,NULL,'stop',15,2.5,1,100,50,10,NULL,NULL,NULL,NULL,'reply');
        """
    )
    db.commit()
    db.close()
    return path

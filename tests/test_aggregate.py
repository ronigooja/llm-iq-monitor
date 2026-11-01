import time
from llm_iq_monitor.db import connect, create_run, insert_result
from llm_iq_monitor.aggregate import percentile, adjust, finalize_run


def test_helpers():
    assert percentile([1, 2, 3, 4], .5) == 2.5
    assert adjust(.01, 20) == 0


def test_finalize():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v1", trigger="manual", dims='["math"]', params="{}", status="running", started_at=now, price_in=.1, price_out=.2, rtt_ms=10)
    insert_result(conn, run, qid="q1", dim="math", correct=1, latency_s=1, ttft_s=.5, in_tok=100, out_tok=200, reasoning_tok=1)
    insert_result(conn, run, qid="q2", dim="math", correct=0, error="empty_reply", latency_s=2, in_tok=100, out_tok=100)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    row = conn.execute("SELECT * FROM run_dims").fetchone()
    assert row["n"] == 2 and row["n_err"] == 1 and row["score"] == 100
    assert conn.execute("SELECT effort_applied,status FROM runs").fetchone()[:2] == (1, "partial")

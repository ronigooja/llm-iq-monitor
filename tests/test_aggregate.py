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
    assert row["n"] == 2 and row["n_err"] == 1 and row["score"] is None
    assert conn.execute("SELECT status FROM runs").fetchone()[0] == "partial"


def test_finalize_ui_and_future_dimensions():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v2", trigger="manual", dims='["ui", "future"]', params="{}", status="running", started_at=now)
    insert_result(conn, run, qid="u1", dim="ui", correct=None, error=None, latency_s=1, ttft_s=.5)
    insert_result(conn, run, qid="f1", dim="future", correct=1, error=None, latency_s=2, ttft_s=1)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    ui = conn.execute("SELECT * FROM run_dims WHERE dim='ui'").fetchone()
    future = conn.execute("SELECT * FROM run_dims WHERE dim='future'").fetchone()
    assert ui["score"] is None and ui["n"] == 1 and ui["n_err"] == 0
    assert future["score"] == 100


def test_finalize_score_uses_answered_questions_at_eighty_percent_boundary():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v2", trigger="manual", dims='["math"]', params="{}", status="running", started_at=now)
    for i in range(18):
        insert_result(conn, run, qid=f"q{i}", dim="math", correct=None if i < 2 else 1,
                      error="timeout" if i < 2 else None, latency_s=1, ttft_s=.5)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    row = conn.execute("SELECT * FROM run_dims").fetchone()
    assert row["score"] == 100
    assert row["n"] == 18 and row["n_err"] == 2


def test_finalize_score_below_eighty_percent_is_null_and_errors_are_not_wrong():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v4", trigger="manual", dims='["math"]', params="{}", status="running", started_at=now)
    for i in range(10):
        insert_result(conn, run, qid=f"q{i}", dim="math", correct=1 if i == 0 else None,
                      error=None if i == 0 else "timeout", latency_s=1)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    assert conn.execute("SELECT score FROM run_dims").fetchone()[0] is None


def test_finalize_ui_scoring_is_unaffected_by_machine_score_rule():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v4", trigger="manual", dims='["ui"]', params="{}", status="running", started_at=now)
    insert_result(conn, run, qid="u1", dim="ui", correct=None, error=None, latency_s=1)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    assert conn.execute("SELECT score FROM run_dims").fetchone()[0] is None


def test_finalize_all_errors_score_null_and_quality_keeps_half_rule():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v2", trigger="manual", dims='["math", "write_en"]', params="{}", status="running", started_at=now)
    for i in range(3):
        insert_result(conn, run, qid=f"m{i}", dim="math", correct=None, error="network_error", latency_s=1, ttft_s=None)
    insert_result(conn, run, qid="w0", dim="write_en", correct=1, error=None, quality=80, latency_s=1, ttft_s=.5)
    insert_result(conn, run, qid="w1", dim="write_en", correct=1, error=None, quality=None, latency_s=1, ttft_s=.5)
    insert_result(conn, run, qid="w2", dim="write_en", correct=1, error=None, quality=None, latency_s=1, ttft_s=.5)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    math = conn.execute("SELECT * FROM run_dims WHERE dim='math'").fetchone()
    writing = conn.execute("SELECT * FROM run_dims WHERE dim='write_en'").fetchone()
    assert math["score"] is None
    assert writing["score"] == 100 and writing["quality"] is None


def test_finalize_empty_run_has_no_scored_questions():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v2", trigger="manual", dims='[]', params="{}", status="running", started_at=now)
    conn.execute("UPDATE runs SET finished_at=? WHERE id=?", (now + 2, run))
    finalize_run(conn, run)
    assert conn.execute("SELECT COUNT(*) FROM run_dims").fetchone()[0] == 0


def test_finalize_preserves_terminal_status():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id,active) VALUES ('m',1)")
    now = time.time()
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v2", trigger="manual", dims="[]", params="{}", status="aborted", started_at=now, finished_at=now + 1)
    finalize_run(conn, run)
    assert conn.execute("SELECT status FROM runs WHERE id=?", (run,)).fetchone()[0] == "aborted"

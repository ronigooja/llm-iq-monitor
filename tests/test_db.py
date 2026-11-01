import sqlite3
from llm_iq_monitor.db import connect, create_run, insert_result, backup, mark_running_aborted


def test_schema_and_helpers(tmp_path):
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id, active) VALUES ('m', 1)")
    run = create_run(conn, model="m", effort="medium", seed="20260101", dataset_version="v1", trigger="manual", dims="[]", params="{}", status="running")
    insert_result(conn, run, qid="q", dim="math", correct=1, error=None)
    assert conn.execute("SELECT count(*) FROM results").fetchone()[0] == 1
    assert mark_running_aborted(conn) == 1
    path = backup(conn, tmp_path)
    assert path.exists()
    assert sqlite3.connect(path).execute("select count(*) from runs").fetchone()[0] == 1

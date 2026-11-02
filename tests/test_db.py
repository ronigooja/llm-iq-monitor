import sqlite3
from llm_iq_monitor.db import (
    connect, create_run, insert_result, backup, mark_running_aborted,
    insert_ui_sample, ui_sample_due,
)


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


def test_ui_samples_and_due_matrix():
    conn = connect(":memory:")
    conn.execute("INSERT INTO models(id, active) VALUES ('m', 1)")
    run = create_run(conn, model="m", effort="medium", seed="s", dataset_version="v2", trigger="manual", dims="[\"ui\"]", params="{}", status="running")
    assert ui_sample_due(conn, "m", "medium", "classic", 7, now=1000)
    first = insert_ui_sample(conn, run, "classic", "p", "<svg/>", True, created_at=100)
    assert not ui_sample_due(conn, "m", "medium", "classic", 7, now=1000)
    conn.execute("UPDATE ui_samples SET stars=7, rated_at=1000 WHERE id=?", (first,))
    assert ui_sample_due(conn, "m", "medium", "classic", 7, now=1000)
    second = insert_ui_sample(conn, run, "classic", "p2", "<svg/>", True, created_at=2000)
    assert conn.execute("SELECT svg FROM ui_samples WHERE id=?", (first,)).fetchone()[0] is None
    assert conn.execute("SELECT stars FROM ui_samples WHERE id=?", (first,)).fetchone()[0] == 7
    assert conn.execute("SELECT svg FROM ui_samples WHERE id=?", (second,)).fetchone()[0] == "<svg/>"

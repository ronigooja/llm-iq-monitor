"""SQLite storage and schema management."""
from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path


SCHEMA_VERSION = 6
UI_HISTORY = 7


def migrate_path() -> Path:
    return Path(os.environ.get("LLM_IQ_DATA_DIR", ".")) / "monitor.db"


def connect(path=None) -> sqlite3.Connection:
    target = path if path is not None else migrate_path()
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(target, timeout=30, isolation_level=None)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA busy_timeout=30000")
    conn.execute("PRAGMA journal_mode=WAL")
    migrate(conn)
    return conn


def migrate(conn: sqlite3.Connection):
    version = conn.execute("PRAGMA user_version").fetchone()[0]
    if version < 1:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS models (
          id TEXT PRIMARY KEY, active INTEGER NOT NULL, first_seen REAL,
          last_seen REAL, last_trigger_at REAL
        );
        CREATE TABLE IF NOT EXISTS prices (
          model TEXT PRIMARY KEY, provider TEXT NOT NULL,
          input_usd_per_m REAL NOT NULL, output_usd_per_m REAL NOT NULL,
          fetched_at REAL NOT NULL
        );
        CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT);
        CREATE TABLE IF NOT EXISTS runs (
          id INTEGER PRIMARY KEY, model TEXT NOT NULL REFERENCES models(id),
          effort TEXT NOT NULL, seed TEXT NOT NULL, dataset_version TEXT NOT NULL,
          trigger TEXT NOT NULL, dims TEXT NOT NULL, params TEXT NOT NULL,
          price_in REAL, price_out REAL, price_fetched_at REAL,
          started_at REAL, finished_at REAL, status TEXT NOT NULL,
           duration_s REAL,
           cost_usd REAL, rtt_ms REAL,
           judge_model TEXT, judge_price_in REAL, judge_price_out REAL
        );
        CREATE TABLE IF NOT EXISTS run_dims (
          run_id INTEGER NOT NULL REFERENCES runs(id), dim TEXT NOT NULL,
           score REAL, n INTEGER, n_err INTEGER,
          latency_p50 REAL, latency_p95 REAL, ttft_p50 REAL,
          time_total REAL, in_tok INTEGER, out_tok INTEGER,
           cost_usd REAL, cost_per_correct REAL,
           quality REAL, judge_cost_usd REAL,
          PRIMARY KEY (run_id, dim)
        );
        CREATE TABLE IF NOT EXISTS results (
          id INTEGER PRIMARY KEY, run_id INTEGER NOT NULL REFERENCES runs(id),
          qid TEXT NOT NULL, dim TEXT NOT NULL, correct INTEGER, error TEXT,
          finish_reason TEXT, latency_s REAL, ttft_s REAL,
          reasoning_ttft_s REAL, in_tok INTEGER, out_tok INTEGER,
           reasoning_tok INTEGER, quality REAL,
           judge_in_tok INTEGER, judge_out_tok INTEGER, judge_latency_s REAL,
           reply TEXT
        );
        CREATE INDEX IF NOT EXISTS runs_model_effort_started ON runs(model, effort, started_at);
        CREATE INDEX IF NOT EXISTS runs_status_finished ON runs(status, finished_at);
        CREATE INDEX IF NOT EXISTS results_run ON results(run_id);
         PRAGMA user_version=1;
         """)
        version = 1
    if version < 2:
        additions = {
            "runs": (("judge_model", "TEXT"), ("judge_price_in", "REAL"), ("judge_price_out", "REAL")),
            "run_dims": (("quality", "REAL"), ("judge_cost_usd", "REAL")),
            "results": (("quality", "REAL"), ("judge_in_tok", "INTEGER"),
                        ("judge_out_tok", "INTEGER"), ("judge_latency_s", "REAL")),
        }
        for table, columns in additions.items():
            existing = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            for name, kind in columns:
                if name not in existing:
                    conn.execute(f"ALTER TABLE {table} ADD COLUMN {name} {kind}")
        conn.execute("PRAGMA user_version=2")
        version = 2
    if version < 3:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS ui_samples (
          id INTEGER PRIMARY KEY,
          run_id INTEGER NOT NULL REFERENCES runs(id),
          prompt_key TEXT NOT NULL,
          prompt TEXT NOT NULL,
          svg TEXT,
          valid INTEGER NOT NULL,
          stars INTEGER,
          rated_at REAL,
          created_at REAL NOT NULL
        );
        CREATE INDEX IF NOT EXISTS ui_samples_run ON ui_samples(run_id);
        CREATE INDEX IF NOT EXISTS ui_samples_stars_created ON ui_samples(stars, created_at);
        """)
        existing = {row[1] for row in conn.execute("PRAGMA table_info(results)")}
        for name, kind in (("http_status", "INTEGER"), ("error_detail", "TEXT")):
            if name not in existing:
                conn.execute(f"ALTER TABLE results ADD COLUMN {name} {kind}")
        conn.execute("PRAGMA user_version=3")
        version = 3
    if version < 4:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS probes (
          id INTEGER PRIMARY KEY, model TEXT NOT NULL, effort TEXT NOT NULL,
          t REAL NOT NULL, ok INTEGER NOT NULL, status INTEGER NULL,
          latency_s REAL NULL, ttft_s REAL NULL, error TEXT NULL
        );
        CREATE INDEX IF NOT EXISTS probes_model_effort_t ON probes(model, effort, t);
        CREATE TABLE IF NOT EXISTS probe_state (
          model TEXT NOT NULL, effort TEXT NOT NULL, state TEXT NOT NULL CHECK(state IN ('busy','idle','unknown')),
          since REAL NOT NULL, updated_at REAL NOT NULL, PRIMARY KEY(model, effort)
        );
        CREATE TABLE IF NOT EXISTS availability_config(window_min INTEGER NOT NULL, min_samples INTEGER NOT NULL, updated_at REAL NOT NULL);
        """)
        conn.execute("PRAGMA user_version=4")
        version = 4
    if version < 5:
        # SQLite cannot drop columns on all supported versions; rebuild the two affected tables.
        conn.executescript("""
        CREATE TABLE runs_new (
          id INTEGER PRIMARY KEY, model TEXT NOT NULL, effort TEXT NOT NULL, seed TEXT NOT NULL,
          dataset_version TEXT NOT NULL, trigger TEXT NOT NULL, dims TEXT NOT NULL, params TEXT NOT NULL,
          price_in REAL, price_out REAL, price_fetched_at REAL, started_at REAL, finished_at REAL,
          status TEXT NOT NULL, duration_s REAL, cost_usd REAL, rtt_ms REAL,
          judge_model TEXT, judge_price_in REAL, judge_price_out REAL
        );
        INSERT INTO runs_new SELECT id,model,effort,seed,dataset_version,trigger,dims,params,price_in,price_out,price_fetched_at,started_at,finished_at,status,duration_s,cost_usd,rtt_ms,judge_model,judge_price_in,judge_price_out FROM runs;
        DROP TABLE runs;
        ALTER TABLE runs_new RENAME TO runs;
        CREATE TABLE run_dims_new (
          run_id INTEGER NOT NULL, dim TEXT NOT NULL, score REAL, n INTEGER, n_err INTEGER,
          latency_p50 REAL, latency_p95 REAL, ttft_p50 REAL, time_total REAL, in_tok INTEGER,
          out_tok INTEGER, cost_usd REAL, cost_per_correct REAL, quality REAL, judge_cost_usd REAL,
          PRIMARY KEY (run_id, dim)
        );
        INSERT INTO run_dims_new SELECT run_id,dim,score,n,n_err,latency_p50,latency_p95,ttft_p50,time_total,in_tok,out_tok,cost_usd,cost_per_correct,quality,judge_cost_usd FROM run_dims;
        DROP TABLE run_dims;
        ALTER TABLE run_dims_new RENAME TO run_dims;
        CREATE INDEX IF NOT EXISTS runs_model_effort_started ON runs(model, effort, started_at);
        CREATE INDEX IF NOT EXISTS runs_status_finished ON runs(status, finished_at);
        CREATE INDEX IF NOT EXISTS results_run ON results(run_id);
        """)
        conn.execute("PRAGMA user_version=5")
        version = 5
    if version < 6:
        conn.execute("""
          CREATE TABLE IF NOT EXISTS availability_runtime (
            now REAL NOT NULL, interval_s REAL NOT NULL, updated_at REAL NOT NULL
          )
        """)
        conn.execute("PRAGMA user_version=6")
        version = 6
    return version


def _insert(conn, table, fields):
    cols = ", ".join(fields)
    marks = ", ".join("?" for _ in fields)
    cur = conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({marks})", [fields[k] for k in fields])
    return cur.lastrowid


def create_run(conn, **fields):
    return _insert(conn, "runs", fields)


def insert_result(conn, run_id, **fields):
    return _insert(conn, "results", {"run_id": run_id, **fields})


def ui_sample_due(conn, model, effort, prompt_key, max_age_days, now=None):
    now = time.time() if now is None else now
    row = conn.execute(
        """
        SELECT s.stars, s.created_at
        FROM ui_samples AS s
        JOIN runs AS r ON r.id = s.run_id
        WHERE r.model=? AND r.effort=? AND s.prompt_key=?
        ORDER BY s.created_at DESC, s.id DESC
        LIMIT 1
        """,
        (model, effort, prompt_key),
    ).fetchone()
    return row is None or row["stars"] is not None or now - row["created_at"] >= max_age_days * 86400


def insert_ui_sample(conn, run_id, prompt_key, prompt, svg, valid, created_at=None):
    created_at = time.time() if created_at is None else created_at
    if svg is not None and len(svg) > 200 * 1024:
        svg, valid = None, 0
    sample_id = _insert(conn, "ui_samples", {
        "run_id": run_id,
        "prompt_key": prompt_key,
        "prompt": prompt,
        "svg": svg,
        "valid": int(bool(valid)),
        "stars": None,
        "rated_at": None,
        "created_at": created_at,
    })
    conn.execute(
        """
        UPDATE ui_samples
        SET svg=NULL
        WHERE id NOT IN (
          SELECT s.id
          FROM ui_samples AS s
          JOIN runs AS r ON r.id=s.run_id
          WHERE r.model=(SELECT model FROM runs WHERE id=?
          ) AND r.effort=(SELECT effort FROM runs WHERE id=?
          ) AND s.prompt_key=?
          ORDER BY s.created_at DESC, s.id DESC
          LIMIT ?
        ) AND prompt_key=? AND run_id IN (
          SELECT old.id
          FROM runs AS old
          JOIN runs AS current ON current.id=?
          WHERE old.model=current.model AND old.effort=current.effort
        )
        """,
        (run_id, run_id, prompt_key, UI_HISTORY, prompt_key, run_id),
    )
    return sample_id


def finish_run(conn, run_id, **fields):
    if not fields:
        return
    setters = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE runs SET {setters} WHERE id=?", [*fields.values(), run_id])


def cleanup_replies(conn, days):
    cutoff = time.time() - days * 86400
    conn.execute("UPDATE results SET reply=NULL WHERE reply IS NOT NULL AND run_id IN (SELECT id FROM runs WHERE finished_at < ?)", (cutoff,))


def cleanup_probes(conn, days=30):
    conn.execute("DELETE FROM probes WHERE t < ?", (time.time() - days * 86400,))


def backup(conn, directory):
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    name = directory / f"monitor-{time.strftime('%Y%m%d-%H%M%S')}.db"
    # sqlite backup is safe while WAL writers are active.
    dest = sqlite3.connect(name)
    try:
        conn.backup(dest)
    finally:
        dest.close()
    files = sorted(directory.glob("*.db"), key=lambda p: p.stat().st_mtime, reverse=True)
    for old in files[7:]:
        old.unlink()
    return name


def mark_running_aborted(conn):
    cur = conn.execute("UPDATE runs SET status='aborted', finished_at=? WHERE status='running'", (time.time(),))
    return cur.rowcount


def repair_last_triggers(conn, tolerance_s=60):
    """Repair trigger timestamps that do not correspond to a started cycle.

    ``last_trigger_at`` used to be written when work was enqueued, while the
    queue itself is process-local.  Keep a timestamp only when a completed
    run started at approximately that trigger; otherwise restore the most
    recent completed run or clear it.  Aborted runs deliberately do not
    count, so they remain eligible on the next heartbeat.
    """
    rows = conn.execute(
        "SELECT id, last_trigger_at FROM models WHERE last_trigger_at IS NOT NULL"
    ).fetchall()
    repaired = 0
    for row in rows:
        trigger = row["last_trigger_at"]
        matched = conn.execute(
            """
            SELECT 1 FROM runs
            WHERE model=? AND status IN ('ok', 'partial', 'unsupported')
              AND started_at >= ? - ?
            ORDER BY started_at DESC LIMIT 1
            """,
            (row["id"], trigger, tolerance_s),
        ).fetchone()
        if matched:
            continue
        previous = conn.execute(
            """
            SELECT MAX(started_at) FROM runs
            WHERE model=? AND status IN ('ok', 'partial', 'unsupported')
            """,
            (row["id"],),
        ).fetchone()[0]
        conn.execute("UPDATE models SET last_trigger_at=? WHERE id=?", (previous, row["id"]))
        repaired += 1
    return repaired

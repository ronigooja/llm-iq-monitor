"""SQLite storage and schema management."""
from __future__ import annotations

import os
import shutil
import sqlite3
import time
from pathlib import Path


SCHEMA_VERSION = 2


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
          availability REAL, duration_s REAL,
           cost_usd REAL, rtt_ms REAL,
           judge_model TEXT, judge_price_in REAL, judge_price_out REAL
        );
        CREATE TABLE IF NOT EXISTS run_dims (
          run_id INTEGER NOT NULL REFERENCES runs(id), dim TEXT NOT NULL,
          score REAL, n INTEGER, n_err INTEGER, availability REAL,
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


def finish_run(conn, run_id, **fields):
    if not fields:
        return
    setters = ", ".join(f"{k}=?" for k in fields)
    conn.execute(f"UPDATE runs SET {setters} WHERE id=?", [*fields.values(), run_id])


def cleanup_replies(conn, days):
    cutoff = time.time() - days * 86400
    conn.execute("UPDATE results SET reply=NULL WHERE reply IS NOT NULL AND run_id IN (SELECT id FROM runs WHERE finished_at < ?)", (cutoff,))


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

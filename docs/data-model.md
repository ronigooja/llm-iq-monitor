# Data model

SQLite, WAL mode, single file at `$DATA_DIR/monitor.db` ([deployment.md](deployment.md#environment)). Field semantics: [metrics.md](metrics.md). Timestamps are Unix seconds, UTC.

## Tables

```sql
models(
  id TEXT PRIMARY KEY,          -- gateway model id
  tier TEXT NOT NULL,           -- 'A' | 'B'
  active INTEGER NOT NULL,      -- 0 when absent from /v1/models
  first_seen REAL, last_seen REAL
);

rounds(
  id INTEGER PRIMARY KEY,
  seed TEXT NOT NULL,
  dataset_version TEXT NOT NULL,
  trigger TEXT NOT NULL,        -- 'schedule' | 'manual'
  started_at REAL, finished_at REAL,
  status TEXT NOT NULL          -- 'running' | 'done' | 'aborted'
);

runs(
  id INTEGER PRIMARY KEY,
  round_id INTEGER NOT NULL REFERENCES rounds(id),
  model TEXT NOT NULL REFERENCES models(id),
  params TEXT NOT NULL,         -- JSON: max_tokens, timeout_s, reasoning/sampling settings actually sent
  started_at REAL, finished_at REAL,
  status TEXT NOT NULL,         -- see metrics.md
  overall REAL, availability REAL, duration_s REAL
);

run_dims(
  run_id INTEGER NOT NULL REFERENCES runs(id),
  dim TEXT NOT NULL,
  score REAL, n INTEGER, n_err INTEGER,
  latency_p50 REAL, latency_p95 REAL, ttft_p50 REAL,
  time_total REAL, out_tok INTEGER,
  PRIMARY KEY (run_id, dim)
);

results(
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  qid TEXT NOT NULL,            -- e.g. 'math-3'
  dim TEXT NOT NULL,
  correct INTEGER, error TEXT, finish_reason TEXT,
  latency_s REAL, ttft_s REAL, in_tok INTEGER, out_tok INTEGER,
  reply TEXT                    -- truncated, see retention
);
```

Indexes: `runs(model, started_at)`, `runs(round_id)`, `results(run_id)`, `rounds(started_at)`.

The dataset version of a run is `rounds.dataset_version` via `runs.round_id`.

## Retention

- `runs`, `run_dims`, `rounds`, `models`: kept forever (small).
- `results` rows: kept forever, without `reply` after 14 days.
- `reply`: stored truncated to 2000 characters; set to null by a daily cleanup after 14 days.
- Reason: free disk on the host is limited ([deployment.md](deployment.md#host)).

## Migrations

Schema version in `PRAGMA user_version`. Migrations are forward-only SQL steps run by the CLI at startup.

## Backup

Nightly `sqlite3 .backup` into `$DATA_DIR/backup/`, keep 7 files.

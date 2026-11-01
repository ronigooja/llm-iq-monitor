# Data model

SQLite, WAL mode, single file at `$LLM_IQ_DATA_DIR/monitor.db` ([deployment.md](deployment.md#environment)). Written by the runner, read by Datasette. Field semantics: [metrics.md](metrics.md), [cost.md](cost.md). Timestamps are Unix seconds, UTC.

## Tables

```sql
models(
  id TEXT PRIMARY KEY,          -- gateway model id
  active INTEGER NOT NULL,      -- 0 when absent from the gateway model list
  first_seen REAL, last_seen REAL,
  last_trigger_at REAL          -- heartbeat tick time of the last triggered cycle
);

prices(
  model TEXT PRIMARY KEY,
  provider TEXT NOT NULL,       -- 'anthropic' | 'openai'
  input_usd_per_m REAL NOT NULL,
  output_usd_per_m REAL NOT NULL,
  fetched_at REAL NOT NULL
);

meta(key TEXT PRIMARY KEY, value TEXT);   -- e.g. price list ETag

runs(
  id INTEGER PRIMARY KEY,
  model TEXT NOT NULL REFERENCES models(id),
  effort TEXT NOT NULL,         -- 'low' | 'medium' | 'high'
  seed TEXT NOT NULL,           -- question seed, YYYYMMDD
  dataset_version TEXT NOT NULL,
  trigger TEXT NOT NULL,        -- 'schedule' | 'manual'
  dims TEXT NOT NULL,           -- JSON list of dimensions run
  params TEXT NOT NULL,         -- JSON: fields actually sent (max_tokens, timeout_s, reasoning_effort)
  price_in REAL, price_out REAL, price_fetched_at REAL,   -- price snapshot
  started_at REAL, finished_at REAL,
  status TEXT NOT NULL,         -- see metrics.md
  effort_applied INTEGER,       -- see metrics.md#effort-support
  overall REAL, availability REAL, duration_s REAL, cost_usd REAL
);

run_dims(
  run_id INTEGER NOT NULL REFERENCES runs(id),
  dim TEXT NOT NULL,
  score REAL, n INTEGER, n_err INTEGER,
  latency_p50 REAL, latency_p95 REAL, ttft_p50 REAL,
  time_total REAL, in_tok INTEGER, out_tok INTEGER,
  cost_usd REAL, cost_per_correct REAL,
  PRIMARY KEY (run_id, dim)
);

results(
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  qid TEXT NOT NULL,            -- e.g. 'math-3'
  dim TEXT NOT NULL,
  correct INTEGER, error TEXT, finish_reason TEXT,
  latency_s REAL, ttft_s REAL, reasoning_ttft_s REAL,
  in_tok INTEGER, out_tok INTEGER, reasoning_tok INTEGER,
  reply TEXT                    -- truncated, see retention
);
```

Indexes: `runs(model, effort, started_at)`, `runs(status, finished_at)`, `results(run_id)`.

`prices`, `runs.price_*` and `results` are not readable through the public API ([api.md](api.md#exposure-rules)).

## Retention

- `models`, `prices`, `runs`, `run_dims`: kept forever (small).
- `results` rows: kept forever, without `reply` after the retention period.
- `reply`: stored truncated to 2000 characters; set to null by the daily maintenance job after `retention.reply_days` ([config.md](config.md#global-settings)).
- Reason: free disk on the host is limited ([deployment.md](deployment.md#host)).

## Migrations

Schema version in `PRAGMA user_version`. Migrations are forward-only SQL steps run by the CLI at startup.

## Backup

The daily maintenance job runs `sqlite3 .backup` into `$LLM_IQ_DATA_DIR/backup/` and keeps 7 files.

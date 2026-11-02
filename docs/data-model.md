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
  availability REAL, duration_s REAL, cost_usd REAL,
  rtt_ms REAL,                  -- see metrics.md#network-round-trip
  judge_model TEXT,             -- writing runs only; null otherwise
  judge_price_in REAL, judge_price_out REAL
);

run_dims(
  run_id INTEGER NOT NULL REFERENCES runs(id),
  dim TEXT NOT NULL,
  score REAL, n INTEGER, n_err INTEGER, availability REAL,
  latency_p50 REAL, latency_p95 REAL, ttft_p50 REAL,
  time_total REAL, in_tok INTEGER, out_tok INTEGER,
  cost_usd REAL, cost_per_correct REAL,
  quality REAL, judge_cost_usd REAL,   -- writing only, see metrics.md#judge
  PRIMARY KEY (run_id, dim)
);

results(
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  qid TEXT NOT NULL,            -- e.g. 'math-3'
  dim TEXT NOT NULL,
  correct INTEGER, error TEXT, finish_reason TEXT,
  latency_s REAL, ttft_s REAL, reasoning_ttft_s REAL,   -- raw times
  in_tok INTEGER, out_tok INTEGER, reasoning_tok INTEGER,
  http_status INTEGER, error_detail TEXT,   -- errors only, never public, see metrics.md#errors
  quality REAL,                 -- writing only
  judge_in_tok INTEGER, judge_out_tok INTEGER, judge_latency_s REAL,
  reply TEXT                    -- truncated, see retention
);
```

ui_samples(
  id INTEGER PRIMARY KEY,
  run_id INTEGER NOT NULL REFERENCES runs(id),
  prompt_key TEXT NOT NULL,     -- 'classic' | 'variant'
  prompt TEXT NOT NULL,         -- the prompt as sent
  svg TEXT,                     -- sanitised SVG; null once the sample is older than the newest 7 of its target and prompt
  valid INTEGER NOT NULL,       -- 0 when the reply failed the SVG rules
  stars INTEGER,                -- 1..10 or null while unrated
  rated_at REAL,
  created_at REAL NOT NULL
);

Indexes: `ui_samples(run_id)`, `ui_samples(stars, created_at)`, `runs(model, effort, started_at)`, `runs(status, finished_at)`, `results(run_id)`.

`prices`, `ui_samples` (only the public queries read it), `runs.price_*`, `runs.judge_*`, `runs.rtt_ms`, `run_dims.judge_cost_usd` and `results` are not readable through the public API ([api.md](api.md#exposure-rules)).

## Retention

- `models`, `prices`, `runs`, `run_dims`: kept forever (small).
- `results` rows: kept forever, without `reply` after the retention period.
- `reply`: stored truncated to 2000 characters; set to null by the daily maintenance job after `retention.reply_days` ([config.md](config.md#global-settings)).
- Reason: free disk on the host is limited ([deployment.md](deployment.md#host)).

## Migrations

Schema version in `PRAGMA user_version`. Migrations are forward-only SQL steps run by the CLI at startup. Step 2 adds the writing and judge columns; step 3 adds `ui_samples` and the error-detail columns of `results` (`http_status`, `error_detail`); existing rows keep null there and all earlier data stays untouched.

## Backup

The daily maintenance job runs `sqlite3 .backup` into `$LLM_IQ_DATA_DIR/backup/` and keeps 7 files.

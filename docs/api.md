# API

Public, read-only, JSON, no authentication. Provided by [Datasette](https://datasette.io) 0.65.5 (Apache-2.0) serving canned queries, not by custom code. Field semantics: [metrics.md](metrics.md), [cost.md](cost.md). There are no write or trigger endpoints.

## Conventions

- Base path `/monitor/`. Each query is `GET /monitor/<name>.json?<params>&_shape=array`. Without `_shape=array` Datasette wraps rows in an object with `ok`, `rows`, `columns`.
- Parameters are strings; an empty or missing optional parameter means "no filter".
- Timestamps: Unix seconds, UTC. Scores 0–100. Latencies in seconds, with the network round trip removed ([metrics.md](metrics.md#network-round-trip)). Costs in USD. Unknown values are `null`, never `0`.
- `Cache-Control: max-age=60`; CORS `*`.
- The SQL of the queries lives in `deploy/metadata.yaml` ([architecture.md](architecture.md#repo-layout)); this doc defines only name, parameters and columns.
- Breaking changes get a new query name; added columns are not breaking.
- There is no overall score. Every query is per dimension.

## Queries

| Name | Parameters | Returns |
|---|---|---|
| `ranking` | `dim` (required: a dimension key, including `write_zh` and `write_en`), `effort` (optional) | Ranking for one capability: the latest finished run of each model × effort that ran the dimension, ordered by score descending, then `latency_p50` ascending, null scores last |
| `series` | `model`, `effort`, `dim` (all required), `from`, `to`, `dataset_version` (optional) | History points, time ascending, at most 2000 rows |
| `models` | none | One row per model × effort that has finished runs |
| `health` | none | Liveness of the pipeline |

Columns:
- `ranking`: `rank` (null when the score is null), `model`, `effort`, `run_id`, `finished_at`, `dataset_version`, `status`, `availability`, `score`, `quality`, `latency_p50`, `latency_p95`, `ttft_p50`, `time_total`, `n`, `n_err`, `cost_usd`, `cost_per_correct`. `quality` is judged, writing dimensions only, null elsewhere ([benchmark.md](benchmark.md#writing-and-judge)); it does not affect `rank`. `availability` is that dimension's `(n − n_err) / n`.
- `series`: `t`, `run_id`, `dataset_version`, `score`, `quality`, `latency_p50`, `latency_p95`, `ttft_p50`, `time_total`, `availability`, `cost_per_correct`.
- `models`: `model`, `effort`, `active`, `dims`, `last_finished_at`, `last_status`.
- `health`: `last_finished_at`, `running_runs`, `prices_fetched_at`.

Runs with status `unsupported`, `aborted` or `running` are excluded from `ranking` and `series`.

## Exposure rules

- Arbitrary SQL, database download and direct table access are disabled; only the queries above are reachable. Verified on Datasette 0.65.5 on 2026-11-02 against a test database: `/monitor.json`, `/monitor/<table>.json` and `/monitor.db` returned 403, canned queries returned 200.
- Never exposed: question text, expected answers, tests, replies, unit prices, price list, raw (unadjusted) times, judge prompts, judge cost. Costs are derived values only ([cost.md](cost.md#price-source)).
- Replies, raw times and price snapshots exist only in tables that are not directly readable ([data-model.md](data-model.md)).
- Abuse control is done at nginx/Cloudflare ([deployment.md](deployment.md#nginx)), not in the app.
- Datasette also renders an HTML page for each canned query; it exposes nothing beyond the JSON.

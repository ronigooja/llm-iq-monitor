# API

Public, read-only, JSON, no authentication. Base path `/api/v1`. Field semantics: [metrics.md](metrics.md). There are no write or trigger endpoints; manual runs use the CLI ([architecture.md](architecture.md#components)).

## Conventions

- Timestamps: Unix seconds, UTC. Scores 0–100. Latencies in seconds.
- Unknown values are `null`, never `0`.
- `Cache-Control: public, max-age=60` on all responses; CORS `*`.
- Errors: HTTP status plus `{"error": "<code>", "message": "<text>"}`.
- Breaking changes go to `/api/v2`; additive fields do not.

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /health` | Liveness, last finished round, whether a round is running |
| `GET /api/v1/dimensions` | Dimension keys, names, question counts, current dataset version |
| `GET /api/v1/models` | Models with tier, active flag, first/last seen |
| `GET /api/v1/latest` | Latest finished run per active model, with per-dimension values |
| `GET /api/v1/series` | History for one model |
| `GET /api/v1/runs/{id}` | One run with per-dimension aggregates (no per-question data) |

### `GET /api/v1/latest`

Query: `tier=A|B` (optional).

```json
{
  "dataset_version": "v1",
  "models": [{
    "model": "claude-sonnet-5-5",
    "tier": "A",
    "run_id": 123,
    "finished_at": 1793500000,
    "overall": 84.2,
    "availability": 1.0,
    "duration_s": 912.4,
    "dims": {
      "math": {"score": 91.7, "latency_p50": 14.2, "latency_p95": 40.1, "ttft_p50": 1.8, "n": 12, "n_err": 0}
    }
  }]
}
```

### `GET /api/v1/series`

Query: `model` (required), `dim` (optional; omit for overall and availability), `from`, `to` (Unix seconds), `dataset_version` (optional), `limit` (default 500, max 2000).

```json
{
  "model": "claude-sonnet-5-5",
  "dim": "math",
  "points": [{"t": 1793500000, "run_id": 123, "dataset_version": "v1",
              "score": 91.7, "latency_p50": 14.2, "latency_p95": 40.1,
              "ttft_p50": 1.8, "time_total": 210.0, "availability": 1.0}]
}
```

Points are ordered by time ascending.

## Exposure rules

- Only aggregates are exposed. Question text, expected answers, tests, and replies are never returned.
- Per-question results are internal ([data-model.md](data-model.md)).
- Abuse control is done at nginx/Cloudflare ([deployment.md](deployment.md#nginx)), not in the app.

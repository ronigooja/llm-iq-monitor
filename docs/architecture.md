# Architecture

## Components

One Python process, one SQLite file.

| Component | Responsibility |
|---|---|
| Scheduler | Fires rounds on the schedule in [scheduling.md](scheduling.md); skips a trigger if the previous round is still running; marks leftover `running` rows as `aborted` on startup |
| Model discovery | At round start, lists the gateway's `/v1/models`, filters non-chat models, assigns tiers |
| Question generator | Builds the question set from a round seed ([benchmark.md](benchmark.md#generation)) |
| Gateway client | Streaming chat completion call; measures latency and time to first token |
| Scorer | Deterministic checkers per question kind ([benchmark.md](benchmark.md#scoring)) |
| Sandbox | Runs model-written code for the code dimension ([deployment.md](deployment.md#code-sandbox)) |
| Aggregator | Writes per-dimension and per-run aggregates ([metrics.md](metrics.md)) |
| Storage | SQLite, WAL mode ([data-model.md](data-model.md)) |
| API | Read-only JSON ([api.md](api.md)) |
| Web | Static files served by the same process ([web.md](web.md)) |
| CLI | Manual trigger, dry run, migrations, backup |

## Data flow

1. Scheduler starts a round and fixes its seed.
2. Discovery returns the models due in this round.
3. Generator builds the questions once; every model gets the same set.
4. Per model (models in parallel up to the limit, questions serial): gateway client → scorer (or sandbox → scorer) → one `results` row per question.
5. Aggregator writes `run_dims` and updates the `runs` row.
6. API and web read only from SQLite.

## Tech stack

Chosen for the target host (1 vCPU, 1.9 GB RAM, Python 3.11; see [deployment.md](deployment.md#host)).

- Python 3.11, FastAPI + uvicorn, httpx (async, streaming), in-process asyncio scheduler.
- SQLite via the standard library. No ORM.
- Web: static HTML, vanilla JS, hand-written SVG charts. No build step, no runtime dependencies.

## Repo layout

Planned. Create directories only when code lands.

```
README.md
AGENTS.md
docs/
src/llm_iq_monitor/
  config.py        env + models config
  discovery.py
  questions/       one module per dimension + registry
  scoring.py
  sandbox.py
  gateway.py
  runner.py
  scheduler.py
  aggregate.py
  db.py            schema + migrations
  api.py
  cli.py
web/               static files
config/models.toml tiers and exclusions (no secrets)
deploy/            systemd unit, env template, nginx note
tests/
```

## Invariants

- Questions, expected answers, and raw replies never leave the host ([api.md](api.md#exposure-rules)).
- A failed request is recorded, never retried ([metrics.md](metrics.md#errors)).
- Core scores never depend on an LLM judge.

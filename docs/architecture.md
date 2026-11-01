# Architecture

Principle: reuse maintained open-source libraries; custom code is limited to question generation, scoring and glue.

## Processes

| Process | Role | Details |
|---|---|---|
| Runner | Heartbeat, scheduling, gateway client, sandbox calls, scoring, aggregation, price refresh, writes SQLite | [deployment.md](deployment.md#services) |
| Web | Datasette: public JSON API and static site, reads SQLite | [api.md](api.md), [web.md](web.md) |
| CLI | `llm-iq-monitor config`, manual run, migrations, backup | Short-lived |

Runner and Web are separate processes sharing one SQLite file in WAL mode, so the site stays up when the runner restarts. Datasette reading while another process writes was verified on 2026-11-02.

## Components (runner)

| Component | Responsibility | Library |
|---|---|---|
| Settings | Parse, validate, merge defaults, hot-reload ([config.md](config.md)) | tomllib, tomli-w, pydantic-settings, watchfiles |
| Scheduler | Heartbeat, price refresh and maintenance jobs ([scheduling.md](scheduling.md#heartbeat)) | APScheduler 3.x |
| Dispatcher | Due check, queue, concurrency limit ([scheduling.md](scheduling.md#due-check)) | asyncio |
| Discovery | Load the model list from `gateway.models_url` | httpx |
| Prices | Daily fetch and cache of the price list ([cost.md](cost.md#price-source)) | httpx |
| Question generator | Build questions from a seed ([benchmark.md](benchmark.md#generation)) | custom |
| Gateway client | Streaming chat completion; latency, time to first token, usage | httpx |
| Scorer | Deterministic checkers ([benchmark.md](benchmark.md#scoring)) | custom |
| Sandbox | Runs model-written code ([deployment.md](deployment.md#code-sandbox)) | Docker |
| Aggregator | Per-dimension and per-run aggregates and cost ([metrics.md](metrics.md), [cost.md](cost.md)) | custom |
| Storage | SQLite ([data-model.md](data-model.md)) | sqlite3 |

## Data flow

1. The heartbeat fires; the dispatcher finds the enabled models that are due and queues them.
2. A worker takes a model: loads the model list, checks the model and its price exist, builds the questions for its dimensions from the date seed.
3. For each selected effort, in order: questions run serially; gateway client → scorer (or sandbox → scorer) → one `results` row per question.
4. The aggregator writes `run_dims` and updates the `runs` row, including cost.
5. Datasette reads SQLite only; the static site calls its JSON queries.

## Dependencies

Versions marked verified were checked on PyPI or npm on 2026-11-02; pin the others to the current stable release when coding.

| Package | Use | Version |
|---|---|---|
| datasette | API and static hosting | 0.65.5 (verified, Python ≥3.10) |
| questionary | Config menu | 2.1.1 (verified) |
| APScheduler | Cron jobs | 3.11.3 (verified). Not 4.x: still alpha |
| httpx | Streaming client, price fetch | 0.28.x |
| pydantic-settings | Settings validation | current 2.x |
| tomli-w | Write `settings.toml` (stdlib `tomllib` only reads) | current |
| watchfiles | Settings hot-reload | current 1.x |
| uPlot | Line charts, vendored into `web/vendor/` | 1.6.32 (verified, MIT) |
| uv | Build and lock the virtualenv | current |

Python 3.11 stdlib: `tomllib`, `sqlite3`, `asyncio`, `subprocess`.

Considered and not used:
- FastAPI/uvicorn: replaced by Datasette canned queries.
- Inspect AI, lm-eval, promptfoo: the runner is thin; per-model dimensions and efforts, time to first token, hidden-test code scoring and the date-seeded generator would all still need glue code, and promptfoo needs Node 22. Revisit Inspect AI if tool-calling or agent tasks are added.
- Redis, Celery, Dramatiq: no queue service needed at this scale.
- OpenAI SDK: httpx gives direct control of streaming and timing with fewer dependencies.

## Repo layout

Planned. Create directories only when code lands.

```
README.md
AGENTS.md
docs/
pyproject.toml, uv.lock
src/llm_iq_monitor/
  settings.py      models for settings.toml, merge, reload
  menu.py          questionary config menu
  scheduler.py     jobs, heartbeat
  dispatcher.py    due check, queue, workers
  discovery.py
  prices.py
  questions/       one module per dimension + registry
  scoring.py
  sandbox.py
  gateway.py
  runner.py        cycle execution
  aggregate.py
  db.py            schema + migrations
  cli.py
web/               index.html, app.js, style.css, vendor/uplot
deploy/
  metadata.yaml    Datasette permissions and canned queries
  *.service        systemd units
tests/
```

## Invariants

- Questions, expected answers, raw replies and unit prices never leave the host ([api.md](api.md#exposure-rules)).
- A failed request is recorded, never retried ([metrics.md](metrics.md#errors)).
- Core scores never depend on an LLM judge.

# llm-iq-monitor

Scheduled benchmark that measures **intelligence**, **runtime** and **cost** of the chat models behind the CLIProxyAPI gateway, keeps the history, and publishes it through a public JSON API and a one-page website at `https://iq.z0e.dev`. Primary consumer: model routers.

Status: design only. No code yet. Open questions: [docs/decisions.md](docs/decisions.md).

## Doc map

Read only what the task needs.

| Doc | Read when |
|---|---|
| [docs/overview.md](docs/overview.md) | Checking scope, non-goals, glossary |
| [docs/architecture.md](docs/architecture.md) | Touching components, data flow, dependencies, repo layout |
| [docs/scheduling.md](docs/scheduling.md) | Touching heartbeat, intervals, concurrency, request parameters, token budget |
| [docs/benchmark.md](docs/benchmark.md) | Touching questions, scoring, dataset versions |
| [docs/metrics.md](docs/metrics.md) | Touching what is recorded or how it is aggregated |
| [docs/cost.md](docs/cost.md) | Touching prices or cost calculation |
| [docs/data-model.md](docs/data-model.md) | Touching SQLite tables or retention |
| [docs/api.md](docs/api.md) | Touching the public API |
| [docs/web.md](docs/web.md) | Touching the website |
| [docs/config.md](docs/config.md) | Touching any setting, its default, or the interactive CLI menu |
| [docs/deployment.md](docs/deployment.md) | Touching the server, nginx, systemd, sandbox, secrets |
| [docs/decisions.md](docs/decisions.md) | Checking what is decided vs open |

Agent rules: [AGENTS.md](AGENTS.md).

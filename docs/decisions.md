# Decisions

## Decided (confirmed by the user)

| Decision | Detail |
|---|---|
| Scope | Intelligence, runtime and cost only ([overview.md](overview.md#scope)). Cost is not ranked |
| Purpose | Model routing |
| Gateway | `ai.nodemgr.uk` is CLIProxyAPI. Base URL `https://ai.nodemgr.uk/v1`, models from `https://ai.nodemgr.uk/v1/models` |
| Scheduling | One global heartbeat cron (default hourly); each model has its own interval, default 6 h, shared by its efforts ([scheduling.md](scheduling.md)) |
| Concurrency | Settable in the menu: models run at the same time, default 3 |
| Per-model settings | Enabled (default off), interval, dimensions (multi), efforts (multi). No A/B tiers ([config.md](config.md#per-model-settings)) |
| Efforts | `low`, `medium`, `high` only; no `default`. A newly enabled model starts with `medium`. Each effort is its own target |
| Question seed | The UTC date |
| Config menu | Interactive CLI menu for the main settings ([config.md](config.md#interactive-menu)) |
| API | Datasette; no hand-built API. Ranking per capability with score, latency and cost ([api.md](api.md)) |
| Website | One page, two tabs: Scores (model cards, one chart each, buttons for capability and effort) and Compare (capability cards, horizontal bar ranking) ([web.md](web.md)) |
| Cost | Shown as cost per correct answer, per capability, as text next to score and latency; no cost ranking. Prices from models.dev, refreshed daily. No alias mapping: models without a price cannot be enabled ([cost.md](cost.md)) |
| Public output | Derived costs only; no unit prices. No attribution or disclaimer text on the site |
| Open source first | Reuse maintained libraries ([architecture.md](architecture.md#dependencies)) |
| Host | `ssh root@50.114.114.252`; nginx for `iq.z0e.dev` already configured ([deployment.md](deployment.md)) |
| Public | API and website are public |
| Third-party leaderboards | No comparison with Artificial Analysis or others |
| Excluded tests | SVG/pelican test |
| Connectivity check | Not needed before building the client |
| Repo | Name `llm-iq-monitor`, location `/Users/zhuwei/Terminal/llm-iq-monitor` |

## Decided by the agent from research (change on request)

| Decision | Basis |
|---|---|
| `reasoning_effort` body field, always sent | CLIProxyAPI source and docs ([scheduling.md](scheduling.md#request-parameters)) |
| Effort support checked in two layers (HTTP 400, then reasoning tokens) | Gateway can silently downgrade or ignore ([metrics.md](metrics.md#effort-support)) |
| Datasette canned queries, Runner and Web as separate processes | Verified locally ([api.md](api.md#exposure-rules)) |
| APScheduler 3.x, jobs not persisted; httpx for streaming; no evaluation framework | [architecture.md](architecture.md#dependencies) |
| Science dimension uses seeded calculation problems, not sampled GPQA | GPQA is public and likely memorised ([benchmark.md](benchmark.md#dimensions)) |
| Interval compared on heartbeat tick times | Avoids drift by one tick ([scheduling.md](scheduling.md#due-check)) |

## Open (defaults apply until the user decides)

| # | Question | Default | Affects |
|---|---|---|---|
| 1 | Code sandbox: one-shot Docker, or nsjail | Docker (already installed), though the runner user then has root-equivalent daemon access | [deployment.md](deployment.md#code-sandbox) |
| 2 | Max output tokens | 8192; thinking models may be truncated, which scores as incorrect | Comparability of thinking models |
| 3 | Remote repo on GitHub (account `ronigooja`): create it, and private or public | Private. Public code would reveal the question generators | Repo |
| 4 | Latency vantage point: host-to-gateway only, or also a second probe location | Host only | [metrics.md](metrics.md#principles) |
| 5 | Show the dimension count when a model runs only some dimensions | Shown on the Overall card ([web.md](web.md#tab-compare)) | Comparability of `overall` |

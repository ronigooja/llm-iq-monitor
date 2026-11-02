# Decisions

## Decided (confirmed by the user)

| Decision | Detail |
|---|---|
| Scope | Intelligence, runtime and cost only ([overview.md](overview.md#scope)). Cost is not ranked |
| Purpose | Model routing, selecting a model per capability |
| No overall score | Only per-dimension scores exist |
| Gateway | `ai.nodemgr.uk` is CLIProxyAPI. Base URL `https://ai.nodemgr.uk/v1`, models from `https://ai.nodemgr.uk/v1/models` |
| Scheduling | One global heartbeat cron (default hourly); each model has its own interval, default 6 h, shared by its efforts ([scheduling.md](scheduling.md)) |
| Concurrency | Settable in the admin console: models run at the same time, default 3 |
| Per-model settings | Enabled (default off), interval, dimensions (multi), efforts (multi). No A/B tiers ([config.md](config.md#per-model-settings)) |
| Efforts | `low`, `medium`, `high` only; no `default`. A newly enabled model starts with `medium`. Each effort is its own target |
| Question seed | The UTC date |
| Max output tokens | Default 16384, adjustable |
| Dimensions for routing | Six: `reasoning`, `code`, `instruction`, `write_zh`, `write_en`, `ui`, each with a "use it when" description so a router can map a task to a dimension. `math` and `science` are legacy and off by default ([benchmark.md](benchmark.md#dimensions)) |
| UI dimension | Pelican-style SVG with a second fixed subject (penguin driving a tractor), the newest 7 samples per target kept, shown on the site, rated 1–10 stars by a person with a rating key; the key is generated on the host ([benchmark.md](benchmark.md#ui-samples), [deployment.md](deployment.md#rating-key)) |
| Pages | Real paths `/`, `/compare`, `/ui`, not `#` routing ([web.md](web.md)) |
| Concurrency | `run.parallel_models` is 1 because the gateway limits capacity |
| Errors | No retries; stream errors void the question; consecutive capacity errors abort the run early ([metrics.md](metrics.md#errors)) |
| Writing dimensions | `write_zh` and `write_en`, 6 questions each, scored separately. Rule checks give `score`; a judge model gives a separate `quality` ([benchmark.md](benchmark.md#writing-and-judge)) |
| Self-judging | Allowed: a model that is the judge still gets a `quality` ([benchmark.md](benchmark.md#writing-and-judge)) |
| Dimension selection | Global default and per model, multi-select, all checked by default ([config.md](config.md#per-model-settings)) |
| Judge | Selectable in the admin console, default `claude-opus-5-5`; effort default `low`. Judge cost and time recorded separately ([config.md](config.md#global-settings)) |
| Network round trip | Measured per run by TCP connect to the gateway, fallback 30 ms (the user measured ping at about 30 ms), subtracted once per request ([metrics.md](metrics.md#network-round-trip)) |
| Latency vantage point | The monitor host only |
| Code sandbox | One-shot Docker containers; the Docker-daemon risk is accepted ([deployment.md](deployment.md#code-sandbox)) |
| Admin console | Web console at `/admin/` replaced the interactive CLI menu (poor multi-select, noisy errors); CLI keeps `config show/get/set/set-key`. Public, admin token, lockout ([deployment.md](deployment.md#admin-console)) |
| API | Datasette; no hand-built API. Ranking per capability with score, latency and cost ([api.md](api.md)) |
| Best router query | Public `best` canned query competes all model × effort candidates per dimension: score tolerance, then price tolerance, then latency/model/effort tie-break; it always returns six display-ordered rows and uses null `model`/`effort` when no candidate remains. Output is `dim`, `use_when`, `model`, `effort` ([api.md](api.md#router-usage)) |
| Website | One page, two tabs: Scores (model cards in alphabetical order, one chart each, buttons for capability and effort) and Compare (capability cards, horizontal bar ranking) ([web.md](web.md)) |
| Cost | Cost per correct answer, per capability, as text next to score and latency; no cost ranking. Prices from models.dev, refreshed daily. No alias mapping: models without a price cannot be enabled ([cost.md](cost.md)) |
| Public output | Derived costs only; no unit prices. No attribution or disclaimer text on the site |
| Open source first | Reuse maintained libraries ([architecture.md](architecture.md#dependencies)) |
| Host | `ssh root@50.114.114.252`; nginx for `iq.z0e.dev` already configured ([deployment.md](deployment.md)) |
| Public | API and website are public |
| Repo | `ronigooja/llm-iq-monitor` on GitHub, public. The user will make it private later. Host address stays in the docs |
| Third-party leaderboards | No comparison with Artificial Analysis or others |
| Excluded tests | Seahorse-emoji questions. The SVG/pelican test is no longer excluded: it is the `ui` dimension with variants, rated by a person |
| Connectivity check | Not needed before building the client |

## Known limits (to revisit with real data)

| Item | State |
|---|---|
| Dataset difficulty | v2 was probed on 2026-11-02 with four models at `low`: `reasoning` and `code` were mostly at full marks (little discrimination), `instruction` spread from 57% to 86%. The user chose to deploy and tune the questions from real data later |
| Capacity | The gateway rejects bursts: `run.parallel_models` is 1 |

## Decided by the agent from research (change on request)

| Decision | Basis |
|---|---|
| `reasoning_effort` body field, always sent | CLIProxyAPI source and docs ([scheduling.md](scheduling.md#request-parameters)) |
| Effort is taken as requested; only an HTTP 400 rejection is recorded as `unsupported`. No check of reasoning tokens or reply content | User decision ([metrics.md](metrics.md#effort-support)) |
| Datasette canned queries, Runner and Web as separate processes | Verified locally ([api.md](api.md#exposure-rules)) |
| APScheduler 3.x, jobs not persisted; httpx for streaming; no evaluation framework | [architecture.md](architecture.md#dependencies) |
| Science dimension uses seeded calculation problems, not sampled GPQA | GPQA is public and likely memorised ([benchmark.md](benchmark.md#dimensions)) |
| Interval compared on heartbeat tick times | Avoids drift by one tick ([scheduling.md](scheduling.md#due-check)) |

## Open

None.

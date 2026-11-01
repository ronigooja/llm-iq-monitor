# Decisions

## Decided (confirmed by the user)

| Decision | Detail |
|---|---|
| Scope | Intelligence and runtime only ([overview.md](overview.md#scope)) |
| Purpose | Model routing |
| Targets | Models of the local cliproxyapi gateway |
| Gateway defaults | Base URL `https://ai.nodemgr.uk/v1`; models loaded from `https://ai.nodemgr.uk/v1/models` ([config.md](config.md#settings)) |
| Configuration | Main settings are editable through an interactive CLI menu ([config.md](config.md#interactive-menu)) |
| Host | `ssh root@50.114.114.252` ([deployment.md](deployment.md#host)) |
| Public | API and web page are public |
| Third-party data | No comparison with Artificial Analysis or other leaderboards |
| Domain and nginx | `iq.z0e.dev`, already configured ([deployment.md](deployment.md#nginx)) |
| Base frequency | Every 6 hours |
| Excluded tests | SVG/pelican test |
| Tier choice | Every model can be assigned to tier A or B individually ([config.md](config.md#settings)) |
| Reasoning effort | Different efforts of a model are all tested, each as its own target ([overview.md](overview.md#glossary)) |
| Connectivity check | Not needed before building the client |
| Repo | Name `llm-iq-monitor`, location `/Users/zhuwei/Terminal/llm-iq-monitor` |

## Open (defaults apply until the user decides)

Tier membership, reasoning effort, token limit, and schedule are now settings in [config.md](config.md#settings), so they can be changed without a code change; only their initial defaults are open.

| # | Question | Default | Affects |
|---|---|---|---|
| 1 | Two-tier schedule (A every 6 h, B daily) or all models every 6 h | Two tiers | [scheduling.md](scheduling.md#tiers), token budget |
| 2 | Initial tier A list | Empty, so every model starts in tier B until set in the menu | `models.tier_a` |
| 10 | How an effort is sent to the gateway: OpenAI `reasoning_effort` field, Anthropic-style thinking budget, or per-effort model aliases exposed by the gateway | Send `reasoning_effort` and let the gateway map it; check the gateway docs or model list before coding | [scheduling.md](scheduling.md#request-parameters) |
| 11 | Efforts to test by default | `default`, `low`, `medium`, `high` for every model; models that reject an effort are recorded as unsupported | [config.md](config.md#settings), token budget |
| 3 | Initial max output tokens | 8192; high efforts may be truncated, which scores as incorrect | Comparability of thinking models |
| 4 | Science dimension: seeded calculation problems, or sampled GPQA multiple choice as first proposed | Seeded calculations (GPQA is public and likely memorised) | [benchmark.md](benchmark.md#dimensions) |
| 5 | Code sandbox: one-shot Docker containers, or host-level `unshare` + unprivileged uid | Docker | [deployment.md](deployment.md#code-sandbox) |
| 6 | Remote repo: create on GitHub (account `ronigooja`), and private or public | Private. Public code would reveal the question generators | Repo |
| 7 | Add a routing helper endpoint (filter and rank by score and latency) | Not in v1; consumers use `/latest` | [api.md](api.md) |
| 8 | Latency vantage point: host-to-gateway only, or also a second probe location | Host only | [metrics.md](metrics.md#principles) |

Resolved by the menu design: who enters the gateway key. The user types it into the menu on the host; the agent never handles it ([deployment.md](deployment.md#secrets)).

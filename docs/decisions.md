# Decisions

## Decided (confirmed by the user)

| Decision | Detail |
|---|---|
| Scope | Intelligence and runtime only ([overview.md](overview.md#scope)) |
| Purpose | Model routing |
| Targets | Models of the local cliproxyapi gateway |
| Host | `ssh root@50.114.114.252` ([deployment.md](deployment.md#host)) |
| Public | API and web page are public |
| Third-party data | No comparison with Artificial Analysis or other leaderboards |
| Domain and nginx | `iq.z0e.dev`, already configured ([deployment.md](deployment.md#nginx)) |
| Base frequency | Every 6 hours |
| Excluded tests | SVG/pelican test |
| Repo | Name `llm-iq-monitor`, location `/Users/zhuwei/Terminal/llm-iq-monitor` |

## Open (defaults apply until the user decides)

| # | Question | Default | Affects |
|---|---|---|---|
| 1 | Two-tier schedule (A every 6 h, B daily) or all models every 6 h | Two tiers | [scheduling.md](scheduling.md#tiers), token budget |
| 2 | Which models are tier A | Current main models; user to pick | `config/models.toml` |
| 3 | Reasoning effort and max output tokens: gateway defaults and 8192, or fixed effort, or one entry per effort level | Gateway defaults, 8192 | Comparability and truncation of thinking models ([scheduling.md](scheduling.md#request-parameters)) |
| 4 | Science dimension: seeded calculation problems, or sampled GPQA multiple choice as first proposed | Seeded calculations (GPQA is public and likely memorised) | [benchmark.md](benchmark.md#dimensions) |
| 5 | Code sandbox: one-shot Docker containers, or host-level `unshare` + unprivileged uid | Docker | [deployment.md](deployment.md#code-sandbox) |
| 6 | Who fills the gateway key on the host | User fills it; the agent never sees it | [deployment.md](deployment.md#secrets) |
| 7 | Remote repo: create on GitHub (account `ronigooja`), and private or public | Private. Public code would reveal the question generators | Repo |
| 8 | Add a routing helper endpoint (filter and rank by score and latency) | Not in v1; consumers use `/latest` | [api.md](api.md) |
| 9 | Latency vantage point: host-to-gateway only, or also a second probe location | Host only | [metrics.md](metrics.md#principles) |
| 10 | Is the gateway reachable from the host, and from which network path | Unverified; check before coding the client | [deployment.md](deployment.md#environment) |

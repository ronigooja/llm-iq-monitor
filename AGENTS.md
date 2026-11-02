# Agent rules

- When writing repository docs: English, concise, define each fact in exactly one doc and link to it elsewhere.
- When deciding whether something belongs in the project: only intelligence, runtime and cost are measured. Scope: [docs/overview.md](docs/overview.md#scope).
- When changing question templates, scoring, or the output protocol: bump the dataset version per [docs/benchmark.md](docs/benchmark.md#dataset-versioning).
- When adding judged (LLM-rated) output: store it in `quality` fields only, never in `score` or ranking order, and keep judge tokens, time and cost out of the tested model's figures ([docs/benchmark.md](docs/benchmark.md#writing-and-judge)).
- When exposing data publicly: derived aggregates only. Never expose question text, expected answers, raw replies (the SVG of UI samples is the only exception), or unit prices ([docs/api.md](docs/api.md#exposure-rules)).
- When showing model-generated SVG or any model output in a page: only as `<img>` from a data URL, never inline in the DOM ([docs/web.md](docs/web.md#page-ui-ui)).
- When adding a user-tunable setting: define it once in [docs/config.md](docs/config.md) and expose it in the admin console. Do not hardcode tunables or repeat their values in other docs.
- When adding functionality: use the maintained open-source libraries in [docs/architecture.md](docs/architecture.md#dependencies) before writing custom code, and record any new dependency there.
- When adding code: follow the layout in [docs/architecture.md](docs/architecture.md#repo-layout).
- When a design choice is not confirmed by the user: record it as open in [docs/decisions.md](docs/decisions.md), not as fact elsewhere.
- When changing the design: align with the user first, then edit docs, then write code.
- Never write secrets into the repo. Never ask for, read, or print the gateway key. Secret handling: [docs/deployment.md](docs/deployment.md#secrets).

# Agent rules

- When writing repository docs: English, concise, define each fact in exactly one doc and link to it elsewhere.
- When deciding whether something belongs in the project: only intelligence and runtime are measured. Scope is defined in [docs/overview.md](docs/overview.md).
- When changing question templates, scoring, or output protocol: bump the dataset version per [docs/benchmark.md](docs/benchmark.md#dataset-versioning).
- When exposing data publicly: aggregates only. Never expose question text, expected answers, or raw replies ([docs/api.md](docs/api.md#exposure-rules)).
- When adding code: follow the layout in [docs/architecture.md](docs/architecture.md#repo-layout).
- When a design choice is not yet confirmed by the user: record it as open in [docs/decisions.md](docs/decisions.md), not as fact elsewhere.
- Never write secrets into the repo. Secret handling: [docs/deployment.md](docs/deployment.md#secrets).

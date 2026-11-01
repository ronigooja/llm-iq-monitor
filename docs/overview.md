# Overview

## Purpose

For each model served by the gateway, periodically measure how smart it is, how long it takes and what it costs, per capability (dimension) and per reasoning effort; keep every measurement; publish the latest values and history. Used by model routers to pick a model.

## Scope

In scope:
- Intelligence score per dimension and overall, per model and effort ([benchmark.md](benchmark.md), [metrics.md](metrics.md)).
- Runtime: per-question latency, time to first token, wall time, availability.
- Cost per correct answer, from real token usage and listed prices ([cost.md](cost.md)).
- History of all of the above.
- Per-model choice of enabled state, interval, dimensions and efforts ([config.md](config.md#per-model-settings)).
- Public read-only JSON API and a one-page website.

Out of scope (do not add):
- Context length, multimodal, safety, throughput benchmarking of the gateway itself.
- Subjective or LLM-judged quality. The SVG/pelican test is excluded.
- Comparison with or ingestion of third-party leaderboards.
- Ranking by cost, or a combined value score. Cost is an auxiliary number next to score and latency.
- Routing itself. Consumers weigh score, latency and cost on their own.

## Targets

- Gateway: CLIProxyAPI, OpenAI-compatible, default base URL in [config.md](config.md#global-settings).
- Public site: `https://iq.z0e.dev`, served from the host in [deployment.md](deployment.md#host).

## Glossary

| Term | Meaning |
|---|---|
| Gateway | The CLIProxyAPI endpoint under test |
| Model | A model id from the gateway's model list |
| Effort | Reasoning effort sent with every request: `low`, `medium` or `high` |
| Target | A model plus an effort, written `model@effort`. The unit that is run, scored and charted |
| Dimension | One of six question groups ([benchmark.md](benchmark.md#dimensions)). Also called capability in the UI |
| Question | One generated prompt with a machine-checkable answer |
| Heartbeat | The single global cron that wakes the runner ([scheduling.md](scheduling.md#heartbeat)) |
| Interval | A model's own time between cycles |
| Cycle | What a model does when it is due: one run per selected effort |
| Run | One target's questions for the model's selected dimensions |
| Result | One answer to one question |
| Dataset version | Label for question templates and scoring rules ([benchmark.md](benchmark.md#dataset-versioning)) |

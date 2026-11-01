# Overview

## Purpose

For each model served by the gateway, periodically measure how smart it is and how long it takes, per dimension, keep every measurement, and publish the latest values and history. Used by model routers to pick a model.

## Scope

In scope:
- Intelligence score per dimension and overall ([benchmark.md](benchmark.md), [metrics.md](metrics.md)).
- Runtime: per-question latency, time to first token, wall time per run, availability.
- History of both, per model and per dimension.
- Public read-only JSON API and a minimal web page.

Out of scope (do not add):
- Price, cost, context length, multimodal, safety, throughput benchmarking of the gateway itself.
- Subjective or LLM-judged quality. The SVG/pelican test is excluded.
- Comparison with or ingestion of third-party leaderboards (Artificial Analysis and similar).
- Routing itself. Consumers combine score and latency with their own weights.

## Targets

- Gateway: cliproxyapi, OpenAI-compatible, base URL in [deployment.md](deployment.md#environment).
- Public site: `https://iq.z0e.dev`, served from the host in [deployment.md](deployment.md#host).

## Glossary

| Term | Meaning |
|---|---|
| Gateway | The cliproxyapi OpenAI-compatible endpoint under test |
| Model | A model id returned by the gateway's `/v1/models` |
| Dimension | One of six question groups ([benchmark.md](benchmark.md#dimensions)) |
| Question | One generated prompt with a machine-checkable answer |
| Round | One scheduled batch; all models in it get identical questions (shared seed) |
| Run | One model's full question set inside one round |
| Result | One model's answer to one question |
| Tier | Schedule class of a model ([scheduling.md](scheduling.md#tiers)) |
| Dataset version | Label for the question templates and scoring rules ([benchmark.md](benchmark.md#dataset-versioning)) |

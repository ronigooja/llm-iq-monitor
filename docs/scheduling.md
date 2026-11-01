# Scheduling

Values live in [config.md](config.md#settings); this doc defines behaviour.

## Tiers

| Tier | Models | Trigger |
|---|---|---|
| A | Models in `models.tier_a` | `schedule.tier_a_cron` |
| B | Every other model from the gateway model list | `schedule.tier_b_cron` |

Defaults of the triggers: [config.md](config.md#settings). A tier-B trigger that coincides with a tier-A trigger runs as one round.

Model discovery:
- Source: `gateway.models_url` at round start.
- Ids matching `models.exclude` are dropped.
- A model absent from the list is marked inactive; its history stays.
- A new model is tier B until added to `models.tier_a`.

## Round execution

- Round seed: the scheduled time, `YYYYMMDDHH` (UTC), shared by all models in the round ([benchmark.md](benchmark.md#generation)).
- Models run in parallel up to `run.parallel_models`. Within a model, questions run one at a time, so a model's own load does not distort its latency.
- If a round is still running at the next trigger, the trigger is skipped and logged.
- On startup, rounds and runs left `running` become `aborted`.
- Manual run: CLI, same code path, `trigger = 'manual'`.

## Request parameters

From `run.timeout_s`, `run.max_tokens`, `run.reasoning_effort` ([config.md](config.md#settings)). Streaming is always on. No retries ([metrics.md](metrics.md#errors)). The values actually sent are stored in `runs.params` ([data-model.md](data-model.md)), so history stays interpretable after a setting changes.

## Token budget

Estimates, not measurements. Replace with measured numbers after the first full round.

Per run (70 questions): input about 12k tokens; output about 25k without extended thinking, about 100k with it; hard cap `70 × run.max_tokens` (573k at the default).

27 models were listed by the gateway on 2026-11-02.

| Plan | Runs per day | Input per day | Output per day |
|---|---:|---:|---:|
| All 27 models every 6 h | 108 | ~1.3M | ~2.7M–10.8M |
| All 27 models once a day | 27 | ~0.33M | ~0.7M–2.7M |
| About 10 in tier A every 6 h, the rest daily | ~57 | ~0.7M | ~1.4M–5.7M |

Monetary cost depends on how the gateway bills and is not estimated here.

# Scheduling

Values live in [config.md](config.md#settings); this doc defines behaviour.

## Tiers

| Tier | Models | Trigger |
|---|---|---|
| A | Models resolved to A | `schedule.tier_a_cron` |
| B | Models resolved to B | `schedule.tier_b_cron` |

Tier resolution and trigger defaults: [config.md](config.md#settings). A tier is assigned per model and applies to all of the model's efforts. A tier-B trigger that coincides with a tier-A trigger runs as one round.

Model discovery:
- Source: `gateway.models_url` at round start.
- Each listed model gets its tier and efforts from [config.md](config.md#settings); models resolved to "not tested" are skipped.
- A model absent from the list is marked inactive; its history stays.
- A new model follows `models.default_tier` until assigned.
- Targets are the models times their efforts.

## Round execution

- Round seed: the scheduled time, `YYYYMMDDHH` (UTC), shared by all models in the round ([benchmark.md](benchmark.md#generation)).
- Targets run in parallel up to `run.parallel_models`, but two efforts of the same model never run at the same time. Within a target, questions run one at a time, so a target's own load does not distort its latency.
- If a round is still running at the next trigger, the trigger is skipped and logged.
- On startup, rounds and runs left `running` become `aborted`.
- Manual run: CLI, same code path, `trigger = 'manual'`.

## Request parameters

From `run.timeout_s`, `run.max_tokens` and the target's effort ([config.md](config.md#settings)). How the effort is sent to the gateway is open: [decisions.md](decisions.md). Streaming is always on. No retries ([metrics.md](metrics.md#errors)). The values actually sent are stored in `runs.params` ([data-model.md](data-model.md)), so history stays interpretable after a setting changes.

## Token budget

Estimates, not measurements. Replace with measured numbers after the first full round.

Per run (70 questions): input about 12k tokens; output about 25k without extended thinking, about 100k with it; hard cap `70 × run.max_tokens` (573k at the default).

Every effort multiplies the cost: with the default four efforts, one model is four runs per round, so token use is about four times the model-only figures. Cut it by setting fewer efforts globally or per model.

27 models were listed by the gateway on 2026-11-02.

Per day, for model-run counts before multiplying by efforts:

| Plan | Runs per day at 1 effort | Input per day | Output per day |
|---|---:|---:|---:|
| All 27 models every 6 h | 108 | ~1.3M | ~2.7M–10.8M |
| All 27 models once a day | 27 | ~0.33M | ~0.7M–2.7M |
| About 10 in tier A every 6 h, the rest daily | ~57 | ~0.7M | ~1.4M–5.7M |

Multiply each row by the number of efforts per model. Example: the last plan with 4 efforts is ~228 runs per day, ~2.8M input, ~5.7M–23M output.

Monetary cost depends on how the gateway bills and is not estimated here.

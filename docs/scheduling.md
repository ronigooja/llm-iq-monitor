# Scheduling

## Tiers

| Tier | Models | Frequency |
|---|---|---|
| A | Current main models listed in `config/models.toml` | every 6 hours: 00:00, 06:00, 12:00, 18:00 UTC |
| B | Every other chat model the gateway lists | once a day: 03:00 UTC |

Not yet confirmed by the user: see [decisions.md](decisions.md).

Model discovery rules:
- Source: gateway `/v1/models` at round start.
- Non-chat models are dropped by the exclusion list in `config/models.toml`.
- A model absent from the list is marked inactive; its history stays.
- A new model starts in tier B until listed in tier A.

## Round execution

- Round seed: the scheduled time, `YYYYMMDDHH` (UTC), shared by all models in the round ([benchmark.md](benchmark.md#generation)).
- Models run in parallel up to 3. Within a model, questions run one at a time, so a model's own load does not distort its latency.
- If a round is still running at the next trigger, the trigger is skipped and logged.
- On startup, rounds and runs left `running` become `aborted`.
- Manual run: CLI, same code path, `trigger = 'manual'`.

## Request parameters

| Parameter | Value |
|---|---|
| Per-question timeout | 600 s |
| Max output tokens | 8192 |
| Streaming | on |
| Retries | none ([metrics.md](metrics.md#errors)) |
| Reasoning and sampling settings | gateway defaults, none sent; the settings actually sent are stored in `runs.params` |

Reasoning and token-limit policy is not final: see [decisions.md](decisions.md).

## Token budget

Estimates, not measurements. Replace with measured numbers after the first full round.

Per run (70 questions): input about 12k tokens; output about 25k without extended thinking, about 100k with it; hard cap 70 × 8192 = 573k.

27 models were listed by the gateway on 2026-11-02.

| Plan | Runs per day | Input per day | Output per day |
|---|---:|---:|---:|
| All 27 models every 6 h | 108 | ~1.3M | ~2.7M–10.8M |
| All 27 models once a day | 27 | ~0.33M | ~0.7M–2.7M |
| About 10 in tier A every 6 h, the rest daily | ~57 | ~0.7M | ~1.4M–5.7M |

Monetary cost depends on how the gateway bills and is not estimated here.

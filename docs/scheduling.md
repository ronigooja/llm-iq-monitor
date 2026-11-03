# Scheduling

Values live in [config.md](config.md); this doc defines behaviour.

## Heartbeat

- One global cron, `schedule.heartbeat_cron`, UTC. It does not run anything by itself; each tick only asks which models are due.
- Jobs (APScheduler 3.x `AsyncIOScheduler`, not persisted): the heartbeat, the daily price refresh ([cost.md](cost.md#price-source)), and a daily maintenance job (reply cleanup and backup, [data-model.md](data-model.md#retention)).
- Job options: `max_instances = 1`, `coalesce = true`, `misfire_grace_time = 15 min`. A tick missed by more than that is dropped; models that were due are simply picked up at the next tick.
- Changing the heartbeat cron in settings rebuilds the heartbeat job on reload.

## Due check

On every tick, for each enabled model, in this order:
1. Skip it if it has no current price ([cost.md](cost.md#price-lookup)) or is absent from the gateway model list.
2. Skip it if its previous cycle is running or queued.
3. It is due if it never ran, or `tick_time − last_trigger_at ≥ interval_h` ([config.md](config.md#per-model-settings)), both times truncated to the whole minute so tick jitter of a few milliseconds cannot delay a run by one heartbeat.

A due model gets `last_trigger_at = tick_time` and is queued. The comparison uses tick times, not the wall-clock start of the cycle, so a cycle that starts late or runs long does not push the next one back by a heartbeat. The interval therefore resolves to the heartbeat period: with an hourly heartbeat, a 6 h interval fires every 6th tick.

Intervals shorter than the heartbeat period behave as one heartbeat period. A newly enabled model is due at the next tick.

## Execution

- Queue: FIFO. Up to `run.parallel_models` models run at once.
- A cycle for a model: for each selected effort, in the order low, medium, high, run the model's selected dimensions. Efforts of one model never overlap; questions within a run are serial, so a model's own load does not distort its latency.
- Question seed: the UTC date of the tick that triggered the cycle ([benchmark.md](benchmark.md#generation)). All models triggered on the same day get identical questions; repeated cycles on the same day repeat the questions, which also exposes run-to-run variance.
- A run aborted by the consecutive-error rule ([metrics.md](metrics.md#errors)) leaves `last_trigger_at` unchanged.
- On startup, runs left `running` become `aborted`; queued work is dropped and recomputed at the next tick.
- Manual run: CLI, same code path, `trigger = 'manual'`, limited to chosen models, ignores intervals.

## Request parameters

Sent to `POST {gateway.base_url}/chat/completions`:

| Field | Value |
|---|---|
| `model` | The model id as listed. The CLIProxyAPI model-name suffix syntax (`model(high)`) is not used: it overrides body fields and would hide the effort from `runs.params` |
| `stream` | `true`, with usage requested in the final chunk |
| `max_tokens` | `run.max_tokens` |
| `reasoning_effort` | `low`, `medium` or `high`; always sent |

The timeout is `run.timeout_s`. No retries ([metrics.md](metrics.md#errors)). The fields actually sent are stored in `runs.params` ([data-model.md](data-model.md)), so history stays interpretable after a setting changes.

Gateway behaviour behind this is taken from CLIProxyAPI v8.0.48 source and docs; the gateway is CLIProxyAPI, the deployed version is not verified. `reasoning_effort` works for GPT and Claude models and is translated to the upstream format. Reasoning text arrives in `delta.reasoning_content`, answer text in `delta.content`, reasoning token count in `usage.completion_tokens_details.reasoning_tokens`.

## Token budget

Estimates, not measurements. Replace with measured numbers after the first full cycle.

Per run (62 questions, all dimensions): input about 10k tokens; output about 20k without extended thinking, about 80k with it; hard cap `62 × run.max_tokens` (about 1.0M at the default). Writing questions add 16 judge calls per run, each about 1k input and under 1k output tokens at `judge.effort = low` (estimate). A run with fewer dimensions scales down proportionally.

```
runs per day = sum over enabled models of (24 / interval_h × selected efforts)
```

The admin console shows these estimates per week (× 7) with K / M units.

Example: 10 models, 6 h interval, 3 efforts each = 120 runs per day, about 1.4M input and 3M–12M output tokens per day. 27 models were listed by the gateway on 2026-11-02; 22 of them have a price ([cost.md](cost.md#price-lookup)).

The admin console shows this estimate ([config.md](config.md#admin-console)). Monetary cost depends on how the gateway bills and is not estimated here.

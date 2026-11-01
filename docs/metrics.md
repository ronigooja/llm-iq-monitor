# Metrics

Single source for what is recorded and how it is aggregated. Table columns: [data-model.md](data-model.md). Cost fields: [cost.md](cost.md).

## Per question (result)

| Field | Definition |
|---|---|
| `correct` | 1 or 0; null when the request errored |
| `error` | null or an error class (below) |
| `finish_reason` | as returned |
| `latency_s` | request start to end of stream (raw) |
| `ttft_s` | request start to first non-empty `delta.content` (answer text) (raw) |
| `reasoning_ttft_s` | request start to first non-empty `delta.reasoning_content`; null if none arrives (raw) |
| `in_tok`, `out_tok` | from the gateway's usage block; null if absent. `out_tok` includes reasoning tokens |
| `reasoning_tok` | `usage.completion_tokens_details.reasoning_tokens`; null if absent |

Times marked raw are stored as measured and adjusted at aggregation ([Network round trip](#network-round-trip)).

## Errors

| Class | Meaning |
|---|---|
| `timeout` | no complete reply within the per-question timeout |
| `http_error` | non-2xx response, including 429 and 5xx |
| `network_error` | connection or stream failure |
| `empty_reply` | stream ended with no content |

Rules:
- No retries. Availability is itself a routing signal.
- An errored question has `correct = null` and is excluded from the score but counted in availability.

### Effort support

A status code alone does not prove the effort took effect, so two checks apply to every run:

1. The gateway rejects the combination with HTTP 400: the run is stored with status `unsupported`, no results, and is excluded from charts and the API. It is not retried until the settings or the model list change.
2. HTTP 200 but `reasoning_tok` is null or zero for every question of the run: the run is kept with `effort_applied = 0`. The gateway may have ignored or downgraded the effort, or the model does not think. The website marks such a target as unverified.

Otherwise `effort_applied = 1`.

## Per dimension (run_dims)

| Field | Definition |
|---|---|
| `score` | `100 × correct / answered`; null when `answered < n / 2` |
| `n`, `n_err` | questions in the dimension, errored questions |
| `availability` | `(n − n_err) / n` |
| `latency_p50`, `latency_p95` | percentiles of adjusted `latency_s` over answered questions |
| `ttft_p50` | median adjusted `ttft_s` over answered questions |
| `time_total` | wall time spent on the dimension, errored questions included |
| `in_tok`, `out_tok` | sums over the dimension's questions |
| `cost_usd`, `cost_per_correct` | see [cost.md](cost.md#calculation) |

"Answered" means not errored.

## Per run

| Field | Definition |
|---|---|
| `availability` | `answered / total questions` |
| `duration_s` | run wall time |
| `status` | `running`, `ok` (no errors), `partial` (some errors), `aborted`, `unsupported` |
| `effort_applied` | see [Effort support](#effort-support) |
| `cost_usd` | sum of dimension costs ([cost.md](cost.md#calculation)) |

## Network round trip

- At the start of each run, the runner opens a TCP connection to the gateway host and port three times and takes the median connect time as `rtt_ms`. If it cannot be measured, `net.rtt_fallback_ms` is used ([config.md](config.md#global-settings)).
- Adjusted time = `max(0, raw − rtt)`, applied once per request to `latency_s`, `ttft_s` and `reasoning_ttft_s`. Raw values stay in `results`; `runs.rtt_ms` keeps the value used.
- Aggregates (`run_dims`) and the API use adjusted times.
- This removes only the monitor-host-to-gateway network part. Gateway-to-provider time stays in, which is what routing cares about.
- Approximation: the connect time is about one round trip; DNS and TLS setup are not removed separately.

## Principles

- Efforts are never averaged or merged: every target has its own series.
- Score, latency, availability and cost are stored separately and never merged into one number. Consumers apply their own weights.
- Latency is measured from the monitor host ([deployment.md](deployment.md#host)) with the host-to-gateway network round trip removed. It still includes the gateway-to-provider path.
- There is no overall score: routing selects per capability ([overview.md](overview.md#scope)).
- Smoothing and moving averages are computed by readers, not stored.

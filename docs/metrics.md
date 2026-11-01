# Metrics

Single source for what is recorded and how it is aggregated. Table columns: [data-model.md](data-model.md). Cost fields: [cost.md](cost.md).

## Per question (result)

| Field | Definition |
|---|---|
| `correct` | 1 or 0; null when the request errored |
| `error` | null or an error class (below) |
| `finish_reason` | as returned |
| `latency_s` | request start to end of stream |
| `ttft_s` | request start to first non-empty `delta.content` (answer text) |
| `reasoning_ttft_s` | request start to first non-empty `delta.reasoning_content`; null if none arrives |
| `in_tok`, `out_tok` | from the gateway's usage block; null if absent. `out_tok` includes reasoning tokens |
| `reasoning_tok` | `usage.completion_tokens_details.reasoning_tokens`; null if absent |

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
| `latency_p50`, `latency_p95` | percentiles of `latency_s` over answered questions |
| `ttft_p50` | median `ttft_s` over answered questions |
| `time_total` | wall time spent on the dimension, errored questions included |
| `in_tok`, `out_tok` | sums over the dimension's questions |
| `cost_usd`, `cost_per_correct` | see [cost.md](cost.md#calculation) |

"Answered" means not errored.

## Per run

| Field | Definition |
|---|---|
| `overall` | mean of non-null dimension scores of the dimensions that were run, equal weights; null if none |
| `availability` | `answered / total questions` |
| `duration_s` | run wall time |
| `status` | `running`, `ok` (no errors), `partial` (some errors), `aborted`, `unsupported` |
| `effort_applied` | see [Effort support](#effort-support) |
| `cost_usd` | sum of dimension costs ([cost.md](cost.md#calculation)) |

Because `overall` covers only the dimensions a model ran, `overall` values of runs with different dimension sets are not comparable. The run stores the dimension list (`runs.dims`) and the API returns the dimension count ([api.md](api.md#queries)).

## Principles

- Efforts are never averaged or merged: every target has its own series.
- Score, latency, availability and cost are stored separately and never merged into one number. Consumers apply their own weights.
- Latency is measured from the monitor host ([deployment.md](deployment.md#host)). It reflects the host-to-gateway path, not the consumer's path.
- Smoothing and moving averages are computed by readers, not stored.

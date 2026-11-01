# Metrics

Single source for what is recorded and how it is aggregated. Table columns: [data-model.md](data-model.md).

## Per question (result)

| Field | Definition |
|---|---|
| `correct` | 1 or 0; null when the request errored |
| `error` | null or an error class (below) |
| `latency_s` | request start to end of stream |
| `ttft_s` | request start to first streamed content delta (answer text, not hidden reasoning) |
| `in_tok`, `out_tok` | from the gateway's usage block; null if absent |
| `finish_reason` | as returned |

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

## Per dimension (run_dims)

| Field | Definition |
|---|---|
| `score` | `100 × correct / answered`; null when `answered < n / 2` |
| `n`, `n_err` | questions in the dimension, errored questions |
| `latency_p50`, `latency_p95` | percentiles of `latency_s` over answered questions |
| `ttft_p50` | median `ttft_s` over answered questions |
| `time_total` | wall time spent on the dimension, errored questions included |
| `out_tok` | sum of output tokens |

"Answered" means not errored.

## Per run

| Field | Definition |
|---|---|
| `overall` | mean of non-null dimension scores, equal weights; null if none |
| `availability` | `answered / total questions` |
| `duration_s` | run wall time |
| `status` | `running`, `ok` (no errors), `partial` (some errors), `aborted` |

## Principles

- Score, latency, and availability are stored separately and never merged into one number. Consumers apply their own weights.
- Latency is measured from the monitor host ([deployment.md](deployment.md#host)). It reflects the host-to-gateway path, not the consumer's path.
- Smoothing and moving averages are computed by readers, not stored.

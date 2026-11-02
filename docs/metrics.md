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
| `quality` | writing only: judged quality 0–100, null when not judged ([benchmark.md](benchmark.md#writing-and-judge)) |
| `judge_in_tok`, `judge_out_tok`, `judge_latency_s` | writing only: the judge call's usage and time; null when not judged |

Times marked raw are stored as measured and adjusted at aggregation ([Network round trip](#network-round-trip)).

## Errors

| Class | Meaning |
|---|---|
| `timeout` | no complete reply within the per-question timeout |
| `http_error` | non-2xx response, including 429 and 5xx, or an error event inside the stream |
| `network_error` | connection or stream failure |
| `empty_reply` | stream ended with no content |
| `truncated_stream` | the stream ended without `[DONE]` and without a finish reason |

Rules:
- No retries. Availability is itself a routing signal.
- An errored question has `correct = null`, counts as wrong in the score, and is counted in availability.
- The HTTP status and the first 300 characters of the error message are stored in `results.http_status` and `results.error_detail`. They are never public ([api.md](api.md#exposure-rules)).
- An error event inside an HTTP 200 stream (a `data:` line whose JSON has an `error` object) makes the whole question an `http_error`; the partial content is not scored. Evidence: CLIProxyAPI emits `data: {"error":{...}}` after a stream has started and does not send `[DONE]` after a truncated stream (checked in its source on 2026-11-02; the deployed gateway version is not verified).
- A run that sees 5 consecutive `http_error` responses with status 429, 502, 503 or 529 stops early with status `aborted` and does not update the model's trigger time, so the model is retried at the next heartbeat tick instead of after its full interval. The gateway was observed returning 502 and 503 under load on 2026-11-02.

### Effort support

The effort is what the request asks for; the effort the model actually used is not verified. Reply content and reasoning token counts are never used to judge it, and results are scored as returned.

The only check: an HTTP 400 whose message says the reasoning level is not supported (contains `not supported` or `unknown level`) marks the run `unsupported`: no results, excluded from charts and the API, not retried until the settings or the model list change. Any other HTTP 400 is an ordinary `http_error`. CLIProxyAPI returns 400 with messages of the form `level "x" not supported, valid levels: ...` or `thinking not supported for this model` (source check, 2026-11-02).

## Per dimension (run_dims)

| Field | Definition |
|---|---|
| `score` | `100 × correct / n`; errored questions count as wrong; null when `n = 0` |
| `n`, `n_err` | questions in the dimension, errored questions |
| `availability` | `(n − n_err) / n` |
| `latency_p50`, `latency_p95` | percentiles of adjusted `latency_s` over answered questions |
| `ttft_p50` | median adjusted `ttft_s` over answered questions |
| `time_total` | wall time spent on the dimension, errored questions included |
| `in_tok`, `out_tok` | sums over the dimension's questions |
| `cost_usd`, `cost_per_correct` | see [cost.md](cost.md#calculation) |
| `quality` | writing only: mean of the non-null per-question `quality`; null when fewer than `n / 2` questions were judged |
| `judge_cost_usd` | writing only: see [cost.md](cost.md#judge-cost) |

"Answered" means not errored. It is used for latency and TTFT percentiles and run availability, not the score denominator.

## Per run

| Field | Definition |
|---|---|
| `availability` | `answered / total questions` |
| `duration_s` | run wall time |
| `status` | `running`, `ok` (no errors), `partial` (some errors), `aborted`, `unsupported` |
| `cost_usd` | sum of dimension costs ([cost.md](cost.md#calculation)) |

## Network round trip

- At the start of each run, the runner opens a TCP connection to the gateway host and port three times and takes the median connect time as `rtt_ms`. If it cannot be measured, `net.rtt_fallback_ms` is used ([config.md](config.md#global-settings)).
- Adjusted time = `max(0, raw − rtt)`, applied once per request to `latency_s`, `ttft_s` and `reasoning_ttft_s`. Raw values stay in `results`; `runs.rtt_ms` keeps the value used.
- Aggregates (`run_dims`) and the API use adjusted times.
- This removes only the monitor-host-to-gateway network part. Gateway-to-provider time stays in, which is what routing cares about.
- Approximation: the connect time is about one round trip; DNS and TLS setup are not removed separately.

## Judge

- Judge calls follow each writing question, serially, inside the run. Their tokens, time and cost are stored in the `judge_*` fields and are never part of `latency_*`, `ttft_p50`, `time_total`, `in_tok`, `out_tok`, `cost_usd` or `cost_per_correct`.
- `runs.duration_s` is wall time and therefore includes judge calls; it is not exposed.
- A failed judge call is not a question error and does not change `n_err` or availability.

## Principles

- Efforts are never averaged or merged: every target has its own series.
- Score, latency, availability and cost are stored separately and never merged into one number. Consumers apply their own weights.
- Latency is measured from the monitor host ([deployment.md](deployment.md#host)) with the host-to-gateway network round trip removed. It still includes the gateway-to-provider path.
- There is no overall score: routing selects per capability ([overview.md](overview.md#scope)).
- `score` never depends on a judge. `quality` exists only for the writing dimensions and is never merged with `score`.
- Smoothing and moving averages are computed by readers, not stored.

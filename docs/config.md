# Configuration

Single source for all settings, their defaults and the admin console. Other docs link here instead of repeating values.

## Storage and precedence

| What | Where | Notes |
|---|---|---|
| Settings | `$LLM_IQ_CONFIG_DIR/settings.toml` | No secrets. Written by the admin console or `config set` |
| Gateway key | `$LLM_IQ_CONFIG_DIR/secrets.env` | Mode 600, owned by the service user. Written by the admin console or `config set-key` only |
| Directories | env `LLM_IQ_CONFIG_DIR`, `LLM_IQ_DATA_DIR` | Defaults in [deployment.md](deployment.md#environment) |

Precedence, highest first: environment variable `GATEWAY_API_KEY` (key only) → files above → built-in defaults.

## Global settings

| Key | Default | Meaning |
|---|---|---|
| `gateway.base_url` | `https://ai.nodemgr.uk/v1` | OpenAI-compatible base URL. The gateway is CLIProxyAPI |
| `gateway.models_url` | `<base_url>/models` (`https://ai.nodemgr.uk/v1/models`) | Where the model list is loaded from |
| `gateway.api_key` | none | Secret; stored in `secrets.env`, never in `settings.toml` |
| `schedule.heartbeat_cron` | `0 * * * *` (UTC) | The single global cron ([scheduling.md](scheduling.md#heartbeat)) |
| `prices.url` | `https://models.dev/api.json` | Price list ([cost.md](cost.md#price-source)) |
| `prices.refresh_cron` | `30 3 * * *` (UTC) | When the price list is refreshed |
| `models.default_interval_h` | 6 | Interval for models without their own |
| `models.default_dims` | all six ([benchmark.md](benchmark.md#dimensions)) | Dimensions for models without their own. `math` and `science` exist as legacy dimensions and are never part of the default |
| `models.default_efforts` | `["medium"]` | Efforts for models without their own |
| `run.parallel_models` | 1 | Models run concurrently ([scheduling.md](scheduling.md#execution)) |
| `run.timeout_s` | 600 | Per-question timeout |
| `run.max_tokens` | 16384 | Max output tokens per question |
| `judge.model` | `claude-opus-5-5` | Model that rates writing quality ([benchmark.md](benchmark.md#writing-and-judge)). Must have a price |
| `judge.effort` | `low` | Reasoning effort sent to the judge: `low`, `medium` or `high` |
| `net.rtt_fallback_ms` | 30 | Network round trip used when it cannot be measured ([metrics.md](metrics.md#network-round-trip)) |
| `ui.sample_max_age_days` | 7 | A target gets a new UI sample for a prompt once the previous one is rated or this old ([benchmark.md](benchmark.md#ui-samples)) |
| `retention.reply_days` | 14 | Days to keep raw replies ([data-model.md](data-model.md#retention)) |

## Per-model settings

Stored as `[models."<model id>"]` tables in `settings.toml`. Each key except `enabled` is optional and falls back to the default named below.

| Key | Falls back to | Meaning |
|---|---|---|
| `enabled` | `false` | Whether the model is tested. A model that was never configured is not tested |
| `interval_h` | `models.default_interval_h` | Hours between cycles. All efforts of the model share it |
| `dims` | `models.default_dims` | Dimensions to run, multi-select |
| `efforts` | `models.default_efforts` | Efforts to test, multi-select from `low`, `medium`, `high`. Each effort is a separate target ([overview.md](overview.md#glossary)) |

Dimension selection: every dimension checkbox (global default and per model) starts fully checked. `models.default_dims` is written to `settings.toml` only when it differs from all dimensions; unset means all, so a dimension added later is included automatically. A per-model `dims` list is explicit and is not extended automatically.

Validation on save:
- URLs and cron expressions parse; `parallel_models` is 1–8; `interval_h` is an integer ≥ 1.
- Dimensions and efforts come from the allowed sets and are non-empty for an enabled model.
- A model without a price cannot be enabled ([cost.md](cost.md#price-lookup)). The judge model must have a price too, and is warned about when absent from the model list.
- Model ids absent from the current model list are warned about, not rejected.
- An interval shorter than the heartbeat period is accepted and behaves as one heartbeat period ([scheduling.md](scheduling.md#due-check)); the console warns about it.

## Admin console

The web console at `/admin/` ([web.md](web.md#page-admin-admin), [deployment.md](deployment.md#admin-console)) edits all settings. It validates with the same `Settings` model as the CLI and writes `settings.toml` and `secrets.env`; the Runner reloads the file by itself ([Applying changes](#applying-changes)).

| Section | Contents |
|---|---|
| Gateway | Base URL, models URL, key (write-only, shown only as set / not set), test connection (HTTP status, model count; never the key) |
| Models | One row per known model: state, price, interval, dimensions, efforts. Models without a price show "no price" and cannot be enabled. Multi-select with bulk apply; refresh the list from the gateway. A newly enabled model gets the defaults |
| Defaults and heartbeat | `schedule.heartbeat_cron` (next five ticks), `models.default_*`, `prices.*` |
| Run limits | Parallel models, timeout, max tokens, round-trip fallback, reply retention |
| Judge | Judge model (only models with a price) and effort; judge calls add cost |
| Overview | Estimated runs and tokens per day ([scheduling.md](scheduling.md#token-budget)) |

The model list does not say which efforts a model accepts, so all three are offered for every model. Unsupported ones are recorded at run time ([metrics.md](metrics.md#effort-support)). Validation errors appear next to the field.

CLI for scripts and emergencies, same validation: `config show`, `config get KEY`, `config set KEY VALUE`, and `config set-key` (key on stdin). `config` alone prints usage.

## Applying changes

The runner watches the settings file (watchfiles). A change is parsed and validated in full; on any error the old settings stay active and the error is logged. On success the new settings apply from the next heartbeat tick, and the heartbeat job is rebuilt if its cron changed. A running cycle is not interrupted.

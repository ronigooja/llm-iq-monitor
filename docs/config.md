# Configuration

Single source for all settings, their defaults and the interactive CLI menu. Other docs link here instead of repeating values.

## Storage and precedence

| What | Where | Notes |
|---|---|---|
| Settings | `$LLM_IQ_CONFIG_DIR/settings.toml` | No secrets. Written by the menu |
| Gateway key | `$LLM_IQ_CONFIG_DIR/secrets.env` | Mode 600, owned by the service user. Written by the menu only |
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
| `models.default_dims` | all eight ([benchmark.md](benchmark.md#dimensions)) | Dimensions for models without their own |
| `models.default_efforts` | `["medium"]` | Efforts for models without their own |
| `run.parallel_models` | 3 | Models run concurrently ([scheduling.md](scheduling.md#execution)) |
| `run.timeout_s` | 600 | Per-question timeout |
| `run.max_tokens` | 16384 | Max output tokens per question |
| `judge.model` | `claude-opus-5-5` | Model that rates writing quality ([benchmark.md](benchmark.md#writing-and-judge)). Must have a price |
| `judge.effort` | `low` | Reasoning effort sent to the judge: `low`, `medium` or `high` |
| `net.rtt_fallback_ms` | 30 | Network round trip used when it cannot be measured ([metrics.md](metrics.md#network-round-trip)) |
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
- An interval shorter than the heartbeat period is accepted and behaves as one heartbeat period ([scheduling.md](scheduling.md#due-check)); the menu warns about it.

## Interactive menu

Command: `llm-iq-monitor config`. Built with questionary (checkbox, select, password, text prompts), so multi-select is native and it works over SSH. Runs against the config directory of the machine it is started on.

| # | Section | Actions |
|---|---|---|
| 1 | Gateway | Edit base URL and models URL; set the key (hidden input, never echoed or printed); test connection |
| 2 | Models | Fetch the list and show each model with its state, interval, dimensions and efforts. Models without a price are shown as "no price" and cannot be checked. Check models to enable them (a newly enabled model gets the defaults); pick one model to edit its interval, dimensions and efforts; apply one choice to several checked models at once |
| 3 | Defaults and heartbeat | `schedule.heartbeat_cron` (shows the next five ticks), `models.default_*`, `prices.*` |
| 4 | Run limits | Parallel models, timeout, max tokens, round-trip fallback, reply retention |
| 5 | Judge | Pick the judge model from the models that have a price (current choice marked); pick the judge effort. Warns that judge calls add cost |
| 6 | Review | Show all settings with the key masked, and the estimated runs and tokens per day ([scheduling.md](scheduling.md#token-budget)) |
| 7 | Quit | Save and exit, or discard |

"Test connection" calls the models URL and reports HTTP status, model count and elapsed time. It never prints the key.

The model list does not say which efforts a model accepts, so the menu offers all three for every model. Unsupported ones are recorded at run time ([metrics.md](metrics.md#effort-support)).

First start with no `settings.toml` opens the menu at section 1.

Scripting equivalents, same validation: `config show`, `config get KEY`, `config set KEY VALUE`. The key can only be set through the menu's hidden prompt or by piping into `config set-key` on stdin.

## Applying changes

The runner watches the settings file (watchfiles). A change is parsed and validated in full; on any error the old settings stay active and the error is logged. On success the new settings apply from the next heartbeat tick, and the heartbeat job is rebuilt if its cron changed. A running cycle is not interrupted.

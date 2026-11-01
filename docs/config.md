# Configuration

Single source for all settings, their defaults, and the interactive CLI menu. Other docs link here instead of repeating values.

## Storage and precedence

| What | Where | Notes |
|---|---|---|
| Settings | `$CONFIG_DIR/settings.toml` | No secrets. Written by the menu |
| Gateway key | `$CONFIG_DIR/secrets.env` | Mode 600, owned by the service user. Written by the menu only |
| Directories | env `LLM_IQ_CONFIG_DIR`, `LLM_IQ_DATA_DIR` | Defaults in [deployment.md](deployment.md#environment) |

Precedence, highest first: environment variable `GATEWAY_API_KEY` (key only) → files above → built-in defaults.

## Settings

| Key | Default | Meaning |
|---|---|---|
| `gateway.base_url` | `https://ai.nodemgr.uk/v1` | OpenAI-compatible base URL |
| `gateway.models_url` | `<base_url>/models` (`https://ai.nodemgr.uk/v1/models`) | Where the model list is loaded from at each round start |
| `gateway.api_key` | none | Secret; stored in `secrets.env`, never in `settings.toml` |
| `models.exclude` | empty | Glob patterns of model ids never tested |
| `models.tier_a` | empty | Model ids in tier A ([scheduling.md](scheduling.md#tiers)) |
| `schedule.tier_a_cron` | `0 */6 * * *` (UTC) | Tier A trigger |
| `schedule.tier_b_cron` | `0 3 * * *` (UTC) | Tier B trigger |
| `run.parallel_models` | 3 | Models tested concurrently |
| `run.timeout_s` | 600 | Per-question timeout |
| `run.max_tokens` | 8192 | Max output tokens per question |
| `run.reasoning_effort` | unset (gateway default) | `unset`, `low`, `medium`, or `high`; sent only when set |
| `retention.reply_days` | 14 | Days to keep raw replies ([data-model.md](data-model.md#retention)) |
| `server.bind` | `127.0.0.1:2839` | API and web listen address ([deployment.md](deployment.md#nginx)) |

Validation on save: URLs parse, cron expressions parse, numbers in range, `models.tier_a` entries are warned about (not rejected) if absent from the current model list.

## Interactive menu

Command: `llm-iq-monitor config`. Plain numbered text menu using only the standard library, so it works over SSH with no extra dependencies. Runs against the config directory of the machine it is started on.

Menu sections:

| # | Section | Actions |
|---|---|---|
| 1 | Gateway | Edit base URL and models URL; set the key (hidden input, never echoed or printed); test connection |
| 2 | Models | Fetch the list; choose tier A by entering numbers or ranges (`1,3,5-8`); edit exclude patterns |
| 3 | Schedule | Edit the two cron expressions; show the next five trigger times |
| 4 | Run limits | Parallelism, timeout, max tokens, reasoning effort |
| 5 | Retention and server | Reply retention days, bind address |
| 6 | Review | Show all settings with the key masked |
| 7 | Quit | Save and exit, or discard |

"Test connection" calls the models URL, reports HTTP status, model count, and elapsed time. It never prints the key.

First start with no `settings.toml` opens the menu directly with section 1.

Scripting equivalents, same validation: `config show`, `config get KEY`, `config set KEY VALUE`. The key can only be set through the menu's hidden prompt or by piping into `config set-key` on stdin.

## Applying changes

The service re-reads the settings file when its modification time changes (checked every 60 s). Changes apply from the next trigger; a running round is not affected. Changing `server.bind` needs a restart.

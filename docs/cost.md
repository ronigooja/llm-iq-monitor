# Cost

Cost is an auxiliary number shown next to score and latency. It is never ranked on its own ([overview.md](overview.md#scope)).

## Price source

- URL: `prices.url`, default `https://models.dev/api.json` ([config.md](config.md#global-settings)).
- Refreshed once a day by `prices.refresh_cron` with a conditional request (`If-None-Match` with the stored ETag). `304` keeps the cache. A failed fetch keeps the previous cache and is logged; it never blocks runs.
- Stored in the `prices` table ([data-model.md](data-model.md)). Public requests never reach models.dev.
- Observed on 2026-11-02: no usage terms, rate limit, or `Last-Modified` header; the repository is MIT-licensed with no separate data licence. For that reason the public API returns derived costs only ([api.md](api.md#exposure-rules)). The site carries no attribution or disclaimer text (user decision, [decisions.md](decisions.md)).

## Price lookup

- A gateway model has a price when its model id exactly equals a model id under the `anthropic` or `openai` provider of the price list (checked in that order).
- Fields used: `cost.input` and `cost.output`, USD per million tokens. The context-tier prices are ignored: questions are short.
- No alias mapping. A model without a price cannot be enabled and is never run; the admin console lists it as "no price" ([config.md](config.md#admin-console)).
- Observed on 2026-11-02: 22 of the gateway's 27 models matched. The five that did not were older Claude models: `claude-3-5-haiku-20241022`, `claude-3-7-sonnet-20250219`, `claude-opus-4-20250514`, `claude-opus-4-1-20250805`, `claude-sonnet-4-20250514`.
- If an enabled model loses its price later, its cycles are skipped and logged; its history stays.

## Calculation

Per dimension, from the dimension's questions that returned usage:

```
cost_usd         = (in_tok × input_price + out_tok × output_price) / 1,000,000
cost_per_correct = cost_usd / correct questions        (null when there are none)
```

- `out_tok` already includes reasoning tokens, which are billed as output.
- Not counted: caching, batch, regional or platform pricing, tool calls, and anything the gateway adds or discounts. The figure is a reference cost at the provider's list price, not what the gateway bills.
- A dimension whose questions all lack usage has null cost.
- Run cost is the sum of the dimension costs. Per run, `cost_per_correct` is not stored; consumers divide.

## Judge cost

- Writing replies are rated by the judge model ([benchmark.md](benchmark.md#writing-and-judge)). Its cost uses the same formula and the judge model's own price from the same list, and is stored as `run_dims.judge_cost_usd`.
- It is never added to `cost_usd` or `cost_per_correct`, which describe the tested model only.
- The judge model must have a price ([config.md](config.md#global-settings)). Its unit prices are snapshotted per run (`runs.judge_price_in`, `runs.judge_price_out`) and not exposed.

## Price snapshot

Every run stores the unit prices it used and when they were fetched (`runs.price_in`, `runs.price_out`, `runs.price_fetched_at`). Costs are computed at the end of the run and never recomputed, so a price change does not rewrite history. Unit prices stay in the database and are not exposed.

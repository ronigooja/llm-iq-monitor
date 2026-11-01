# Web

Minimal, static, no build step, no runtime dependencies. Data comes only from the public API ([api.md](api.md)).

## Style rules

- Black text on white, system font stack, one accent colour, no icons, no images, no animation.
- JavaScript is required; there is no static fallback.
- Dark mode via `prefers-color-scheme`, same layout.
- Mobile: single column.

## Pages

### `/` Overview

- One table. Rows: active models sorted by `overall` descending. Columns: model, overall, availability, then one column per dimension.
- Each dimension cell shows `score · p50 latency`, for example `91.7 · 14s`.
- Tier B models are shown dimmed. Columns sortable by click.
- Footer: dataset version, last round time.

### `/m/{model}` Model page

- Header: model id, latest overall, availability, last run time.
- Range switch: 7d, 30d, 90d, all.
- One block per dimension plus overall: two small line charts side by side — score history and latency p50 history.
- One availability chart at the bottom.

## Charts

- Hand-written SVG, shared time axis within a page.
- Score axis fixed 0–100; latency axis auto, linear.
- Gaps for null values, not zero.
- Vertical dashed line where `dataset_version` changes, labelled with the new version.
- Hover shows value and time; no legend needed (one series per chart).

## Not shown

Question text, answers, replies, per-question results ([api.md](api.md#exposure-rules)).

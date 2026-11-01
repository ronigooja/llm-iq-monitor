# Web

One static page served by Datasette (`--static` for assets, a template override for `/`). No build step. Data comes only from the public queries ([api.md](api.md)). There are no other pages: no model detail page.

## Style rules

- Black text on white, system font stack, one accent colour, no icons, no images, no animation.
- Dark mode via `prefers-color-scheme`, same layout. Mobile: single column.
- JavaScript is required; there is no static fallback.
- Line charts: uPlot, vendored in `web/vendor/` (no CDN). Bar rankings: plain HTML/CSS.
- No attribution or disclaimer text.

## Layout

Top of the page: two tabs, **Scores** and **Compare**, the tab in the URL hash (`#scores`, `#compare`), and a range switch (7d, 30d, 90d, all) for the Scores tab. Footer: dataset version and time of the last finished run.

## Tab: Scores

- Model cards stacked vertically, ordered by the model's best `overall` across efforts, descending. Models without finished runs are not shown.
- Each card has a header (model id, latest overall, availability, last run time), two button rows, and one chart.
  - Capability buttons: `Overall` and the six dimensions.
  - Effort buttons: the efforts the model has runs for. Initial effort: `medium`, else `high`, else `low`.
- The chart shows the selected capability and effort over time: score as a solid line on the left axis (fixed 0–100), latency p50 as a dashed line on the right axis (auto, linear). Overall has no latency line; it uses run duration instead.
- A card loads its data (`series`, plus `ranking` for the header) when it scrolls into view.
- A target with `effort_applied = 0` is marked "effort unverified".

## Tab: Compare

- Capability cards stacked vertically: `Overall` first, then the six dimensions.
- Each card is a horizontal ranking from the `ranking` query for that capability: one row per model × effort, ordered by rank, latest run of each. Rows without a score show no bar and are listed last.
- A row shows: rank, `model@effort`, a bar whose length is the score (scale 0–100), a dot on the same track positioned by latency p50 on the card's own latency axis (0 to the card's maximum, drawn above the bars), and text at the end of the row: `score · latency · $cost per correct`, for example `91.7 · 14s · $0.012`. A null cost shows `—`.
- Rows with `effort_applied = 0` carry the "effort unverified" mark; rows whose run covers fewer dimensions than others show the `dims_run` count on the `Overall` card.
- Cost is text only. It is not a sort key or a chart ([overview.md](overview.md#scope)).

## Charts

- Gaps for null values, not zero.
- A vertical dashed line where `dataset_version` changes, labelled with the new version.
- Hover shows value and time.

## Not shown

Question text, answers, replies, per-question results, unit prices ([api.md](api.md#exposure-rules)).

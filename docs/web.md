# Web

Public pages served by Datasette use real paths: Home, Compare, UI, Availability and API. Data comes only from the public queries ([api.md](api.md)). No model detail page or build step.

## Style rules

- Black text on white, system font stack, one accent colour, no icons, no images, no animation.
- Dark mode via `prefers-color-scheme`, same layout. Mobile: single column.
- JavaScript is required; there is no static fallback.
- Line charts: uPlot, vendored in `web/vendor/` (no CDN). Bar rankings: plain HTML/CSS.
- No attribution or disclaimer text.
- Latency is shown as "time to solve" (request start to end of reply, thinking included, network round trip removed), not as network delay. The Compare page carries a one-line legend.
- Capabilities are the six dimensions ([benchmark.md](benchmark.md#dimensions)). There is no overall score.

## Cache

Cloudflare caches `/static/*` for hours. After changing any file in `web/`, bump the `?v=` query on its URL in every template under `deploy/templates/`.

## Layout

All pages share one header (title, page links **Scores**, **Compare**, **UI**, **API**; the current one is highlighted; language switch) and one footer (dataset version, time of the last finished run). The range switch (7d, 30d, 90d, all) appears on Scores only. The Compare page and the UI page each have their own script; `app.js` holds the shared helpers.

## Language

English and Simplified Chinese, switched by the `English / 中文` buttons in the header. The first visit follows `navigator.language` (`zh*` gives Chinese); the choice is kept in `localStorage` key `lang`. `web/i18n.js` is loaded before `app.js` and exposes `window.i18n` (`lang`, `setLang`, `t`, `add`, `apply`); static text carries `data-i18n="key"`, page scripts register their strings with `i18n.add({en, zh})` and re-render on the `langchange` event. Model ids, numbers, units, effort keys and API field names are never translated. Chinese dimension names and "use it when" texts are keyed `dim.<dim>.name` / `dim.<dim>.use` and replace the `dimensions` query text in Chinese mode.

## Title and description

Each page has a static bilingual `<title>`, `<meta name="description">` and `og:*` tags (Chinese and English in one string), because crawlers and link previews do not run JavaScript. In the browser, `i18n.js` replaces the title and description with one language on load and on `langchange` (keys `meta.title`, `meta.description` per page). No interval or other changing setting is written in them.

## Dimension names

Buttons and cards use the names from the `dimensions` query: the dimension key plus its "use it when" text as a tooltip. `write_zh` is shown as "Writing · 中文", `write_en` as "Writing · English", `ui` as "Drawing (SVG)".

## Page: Scores (`/`)

- Model cards stacked vertically, ordered alphabetically by model id. Models without finished runs are not shown.
- Each card has a header (model id, availability, last run time), two button rows, and one chart.
  - Capability buttons: the dimensions the model has runs for (up to six). Initial: the first in dimension order.
  - Effort buttons: the efforts the model has runs for. Initial: `medium`, else `high`, else `low`.
- The chart shows the selected capability and effort over time: score as a solid line on the left axis (fixed 0–100), latency p50 as a dashed line on the right axis (auto, linear). The legend hides uPlot's time entry, shows round markers like the chart points and has no trailing colon after names. For `write_zh` and `write_en`, `quality` is added as a dotted line on the left axis and labelled "judged".
- A card loads its data (`series`, plus `ranking` for the header) when it scrolls into view.

## Page: Compare (`/compare`)

- Capability cards stacked vertically, one per dimension with data, in dimension order. Every row shows score, latency p50 and cost per correct; `ui` scores are stars × 10 and its cost is the run's total `cost_usd` marked `total`, because `ui` has no correct count. The latency dot uses the same track for every dimension.
- Each card is a horizontal ranking from the `ranking` query for that capability: one row per model × effort, ordered by rank, latest run of each. Rows without a score show no bar and are listed last.
- A row shows: rank, `model@effort`, a bar whose length is the score (scale 0–100), a dot on the same track positioned by latency p50 on the card's own latency axis (0 to the card's maximum), and text at the end of the row: `score · latency · $cost per correct`, for example `91.7 · 14s · $0.012`. Writing rows add the judged value as `score · quality (judged) · latency · $cost`, for example `83.3 · 78 judged · 14s · $0.012`; `quality` never changes row order. A null cost shows `—`.
- Cost is text only. It is not a sort key or a chart ([overview.md](overview.md#scope)).

## Page: UI (`/ui`)

- Two sections by question, classic then variant, each headed by its subject (the full prompt is a tooltip). Within each section, cards are ordered by the stars on the displayed newest sample, highest first, with unrated cards last; ties retain model id ascending, then low, medium, high. One card per model and effort (effort labels are not translated): the newest valid SVG as an image, model and effort, and the stars (read-only by default). A card shows a placeholder only when the model has no valid sample for that question. The order is recalculated after each render, including after rating.
- History: a card's `◷` symbol (plain glyph, no button frame) loads that card's older samples on demand (`ui_samples` with `model` and `effort`) and opens an overlay directly below the card, spanning the sample grid, so neighbouring cards do not move. It shows up to 4 older samples as cards identical to the main cards (image, date and time in place of the model line, the same star controls), 5 samples in total with the newest; same retention as [benchmark.md](benchmark.md#ui-samples). Esc, a click outside the overlay, or the card's symbol closes it.
- Rating key: a field at the bottom of the page. The key is checked with the `rate` query's authentication ([api.md](api.md#exposure-rules)); if accepted, the page keeps the key in `sessionStorage` (not a cookie, not in the URL) and every sample gets 10 clickable stars. A wrong key shows "key not accepted" and nothing changes.
- After a click the page sends `rate`, then reads the sample back and shows the stored stars, because an out-of-range value changes nothing.
- SVG is never inlined into the page DOM: it is set as `<img src="data:image/svg+xml;...">`, so scripts and external loads inside it do not run. The page also sets a strict `Content-Security-Policy` (no inline scripts except the page's own file, `img-src data:`).

## Page: Availability (`/availability`)

Bilingual. Show one row per model × effort sorted by model and low/medium/high, with current availability, a busy/idle/unknown state chip, and a colored 24-hour strip. Use `availability_history` for a 1-day hourly range or 7/30-day daily, time-weighted buckets. Empty buckets are blank. This page-only query is not in the public API table.

## Charts

- Gaps for null values, not zero.
- A vertical dashed line where `dataset_version` changes, labelled with the new version.
- Hover shows value and time.

## Not shown

Question text, answers, replies, per-question results, unit prices ([api.md](api.md#exposure-rules)).

## Page: API (`/api`)

Public reference built from [api.md](api.md): every query with purpose, parameters, columns and a live example link with a "Try it" button (first three rows, rendered as text). Quick start, field semantics and exposure rules are static text; the dimensions table is loaded from the `dimensions` query. `rate` and `whoami` are listed as owner-only. Same CSP as the UI page.

## Page: Admin (`/admin/`)

Served by the admin service, not Datasette ([deployment.md](deployment.md#admin-console)). One page, `noindex`, bilingual with the site's language switch; effort labels untranslated. Login form (admin token) until a session exists. Sections and fields are in [config.md](config.md#admin-console). A sticky bar shows unsaved changes with Save and Discard; 422 errors appear inline at the field (`data-field` is the dotted settings path). Assets `web/admin.{html,js,css}` are served from a fixed whitelist under `/admin/static/`; strict CSP, no inline script or style.

A tab bar at the top of the console switches between **Settings** (all fields, the sticky save bar) and **Run status**. Run status is a separate tab so that its 15 s refresh never touches a form being edited; it refreshes only while its tab is visible. It reads `/admin/api/status` and shows one enabled model × selected effort row: running progress (finished result count / `DIM_COUNTS` total), last run status and time, next due time, deferred state, and latest probe state, timestamp, result, latency, current availability and sample count.

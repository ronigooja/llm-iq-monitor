const AV_EFFORT_ORDER = ['low', 'medium', 'high'];
const AV_RANGES = { '1d': { days: 1, hourly: true }, '7d': { days: 7, hourly: false }, '30d': { days: 30, hourly: false } };
const AV_STATES = ['busy', 'idle', 'unknown'];
const AV_CONCURRENCY = 4;

function avLevel(value) {
  if (value == null || Number.isNaN(Number(value))) return 'none';
  const v = Number(value);
  if (v >= 0.99) return 'good';
  if (v >= 0.95) return 'ok';
  if (v >= 0.9) return 'warn';
  if (v >= 0.75) return 'low';
  return 'bad';
}
function avPercent(value) {
  return value == null || Number.isNaN(Number(value)) ? '—' : `${(Number(value) * 100).toFixed(1)}%`;
}
function avBucketLabel(seconds, hourly, locale) {
  const date = new Date(Number(seconds) * 1000);
  return hourly ? date.toLocaleString(locale, { month: 'numeric', day: 'numeric', hour: '2-digit', minute: '2-digit' }) : date.toLocaleDateString(locale);
}
function avRank(effort) {
  const index = AV_EFFORT_ORDER.indexOf(effort);
  return index < 0 ? AV_EFFORT_ORDER.length : index;
}
function avSortRows(rows) {
  return [...rows].sort((a, b) => a.model.localeCompare(b.model) || avRank(a.effort) - avRank(b.effort));
}
function avState(value) {
  return AV_STATES.includes(value) ? value : 'unknown';
}
function avLimiter(limit) {
  let active = 0;
  const queue = [];
  const next = () => {
    if (active >= limit || !queue.length) return;
    active += 1;
    const job = queue.shift();
    job().finally(() => { active -= 1; next(); });
  };
  return { run: task => new Promise((resolve, reject) => { queue.push(() => Promise.resolve().then(task).then(resolve, reject)); next(); }) };
}

if (typeof window !== 'undefined') Object.assign(window, { availabilityHelpers: { AV_RANGES, AV_CONCURRENCY, avLevel, avPercent, avBucketLabel, avSortRows, avState, avLimiter } });

if (typeof document !== 'undefined' && document.querySelector('#av-rows')) (async () => {
  const body = document.querySelector('#av-rows'), message = document.querySelector('#av-message');
  const gate = avLimiter(AV_CONCURRENCY);
  const histories = new Map();
  let range = '1d', rows = [], runId = 0;
  const locale = () => (i18n.lang() === 'zh' ? 'zh-CN' : 'en');
  const days = () => AV_RANGES[range].days;
  const keyOf = (row, d) => `${row.model}\0${row.effort}\0${d}`;
  function stateChip(row) {
    const state = avState(row.state);
    return `<span class="av-chip av-${state}" title="${esc(when(row.last_probe_at))}">${esc(tr(`av.state.${state}`))}</span>`;
  }
  function strip(row) {
    const entry = histories.get(keyOf(row, days()));
    if (!entry) return `<span class="muted">${esc(tr('status.loading'))}</span>`;
    if (entry === 'error') return `<span class="muted">${esc(tr('av.historyFailed'))}</span>`;
    if (!entry.length) return `<span class="muted">${esc(tr('status.noDataRangeShort'))}</span>`;
    const hourly = AV_RANGES[range].hourly;
    return `<span class="av-strip">${entry.map(bucket => `<span class="av-cell av-lvl-${avLevel(bucket.availability)}" title="${esc(tr('av.cellTitle', { time: avBucketLabel(bucket.bucket_start, hourly, locale()), pct: avPercent(bucket.availability), n: bucket.samples ?? 0 }))}"></span>`).join('')}</span>`;
  }
  function rowHtml(row, index) {
    return `<tr><th scope="row">${esc(row.model)}</th><td>${esc(row.effort)}</td><td class="num">${avPercent(row.availability)}</td><td>${stateChip(row)}</td><td class="num">${secs(row.latency_p50)}</td><td class="av-history" data-index="${index}">${strip(row)}</td></tr>`;
  }
  function render() {
    body.innerHTML = rows.length ? rows.map((row, index) => rowHtml(row, index)).join('') : `<tr><td colspan="6" class="muted">${esc(tr('av.noRows'))}</td></tr>`;
  }
  function updateStrip(index) {
    const cell = body.querySelector(`td.av-history[data-index="${index}"]`);
    if (cell) cell.innerHTML = strip(rows[index]);
  }
  async function loadHistories() {
    const current = ++runId, d = days(), target = rows;
    await Promise.all(target.map((row, index) => {
      const key = keyOf(row, d);
      if (histories.has(key)) return null;
      return gate.run(async () => {
        if (current !== runId) return;
        try {
          const data = await api('availability_history', { model: row.model, effort: row.effort, days: d });
          histories.set(key, data.slice().sort((a, b) => a.bucket_start - b.bucket_start));
        } catch (_) { histories.set(key, 'error'); }
        if (current === runId) updateStrip(index);
      });
    }));
  }
  async function load() {
    runId += 1;
    try { rows = avSortRows(await api('availability_now')); } catch (_) { rows = []; body.innerHTML = ''; message.textContent = tr('av.loadFailed'); return; }
    message.textContent = '';
    render();
    await loadHistories();
  }
  document.querySelectorAll('[data-av-range]').forEach(button => button.addEventListener('click', () => {
    range = button.dataset.avRange;
    document.querySelectorAll('[data-av-range]').forEach(item => item.setAttribute('aria-selected', String(item === button)));
    render();
    loadHistories();
  }));
  document.addEventListener('langchange', () => render());
  await Promise.all([loadFooter().catch(() => {}), load()]);
})();

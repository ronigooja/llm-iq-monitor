const EFFORT_ORDER = ['low', 'medium', 'high'];
const RANGE_DAYS = { '7d': 7, '30d': 30, '90d': 90 };
const state = { range: '30d', dimensions: [] };
const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&':'&amp;', '<':'&lt;', '>':'&gt;', '"':'&quot;', "'":'&#39;' }[c]));
const num = (v, digits = 1) => v == null ? '—' : Number(v).toFixed(digits);
const secs = v => v == null ? '—' : `${Number(v).toFixed(v < 10 ? 1 : 0)}s`;
const usd = v => v == null ? '—' : `$${Number(v).toFixed(v < 0.01 ? 4 : 3)}`;
const when = t => t ? new Date(t * 1000).toLocaleString(i18n.lang() === 'zh' ? 'zh-CN' : 'en') : '—';
const tr = (key, vars) => i18n.t(key, vars);
const dimName = d => tr(`dim.${d.dim}.name`) === `dim.${d.dim}.name` ? d.name : tr(`dim.${d.dim}.name`);
const dimUse = d => tr(`dim.${d.dim}.use`) === `dim.${d.dim}.use` ? d.use_when : tr(`dim.${d.dim}.use`);
const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();
async function api(name, params = {}, options = {}) {
  const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));
  const q = new URLSearchParams({ ...clean, _shape: 'array' });
  const r = await fetch(`/monitor/${name}.json?${q}`, options);
  if (!r.ok) throw new Error(`${name}: ${r.status}`);
  return r.json();
}
function groupModels(rows) {
  const groups = new Map();
  for (const row of rows) {
    if (!groups.has(row.model)) groups.set(row.model, { model: row.model, efforts: new Map(), dims: new Set() });
    const g = groups.get(row.model); g.efforts.set(row.effort, row);
    (row.dims || '').split(',').filter(Boolean).forEach(d => g.dims.add(d));
  }
  return [...groups.values()].sort((a, b) => a.model.localeCompare(b.model));
}
function initialEffort(g) { return ['medium', 'high', 'low'].find(e => g.efforts.has(e)); }
async function loadDimensions() {
  state.dimensions = await api('dimensions');
  return state.dimensions;
}
async function loadFooter() {
  const health = (await api('health'))[0] || {};
  const last = document.querySelector('#last-run'); if (last) last.textContent = when(health.last_finished_at);
  const dataset = document.querySelector('#dataset'); if (dataset) dataset.textContent = health.dataset_version || '—';
}
function versionMarks(rows) {
  return rows.reduce((out, r, i) => { if (i && r.dataset_version !== rows[i - 1].dataset_version) out.push([r.t, r.dataset_version]); return out; }, []);
}

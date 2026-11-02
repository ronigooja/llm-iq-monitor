(() => {
  const DIMS = ['trap', 'math', 'logic', 'code', 'instruction', 'science'];
  const EFFORT_ORDER = ['low', 'medium', 'high'];
  const RANGE_DAYS = { '7d': 7, '30d': 30, '90d': 90 };
  const state = { range: '30d', models: new Map() };

  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  const num = (v, digits = 1) => (v == null ? '—' : Number(v).toFixed(digits));
  const secs = v => (v == null ? '—' : `${Number(v).toFixed(v < 10 ? 1 : 0)}s`);
  const usd = v => (v == null ? '—' : `$${Number(v).toFixed(v < 0.01 ? 4 : 3)}`);
  const when = t => (t ? new Date(t * 1000).toLocaleString() : '—');
  const css = name => getComputedStyle(document.documentElement).getPropertyValue(name).trim();

  async function api(name, params = {}) {
    const clean = Object.fromEntries(Object.entries(params).filter(([, v]) => v !== '' && v != null));
    const q = new URLSearchParams({ ...clean, _shape: 'array' });
    const r = await fetch(`/monitor/${name}.json?${q}`);
    if (!r.ok) throw new Error(`${name}: ${r.status}`);
    return r.json();
  }

  function button(label, attrs = '') { return `<button ${attrs}>${esc(label)}</button>`; }

  function setTab(tab) {
    const selected = tab === 'compare' ? 'compare' : 'scores';
    if (location.hash.slice(1) !== selected) history.replaceState(null, '', `#${selected}`);
    document.querySelectorAll('.tab').forEach(x => { x.hidden = x.id !== selected; });
    document.querySelectorAll('[data-tab]').forEach(x => x.setAttribute('aria-selected', x.dataset.tab === selected));
    document.querySelector('#ranges').hidden = selected !== 'scores';
    if (selected === 'compare' && !document.querySelector('#compare').dataset.loaded) loadCompare();
  }

  function groupModels(rows) {
    const groups = new Map();
    for (const row of rows) {
      if (!groups.has(row.model)) groups.set(row.model, { model: row.model, efforts: new Map(), dims: new Set() });
      const g = groups.get(row.model);
      g.efforts.set(row.effort, row);
      (row.dims || '').split(',').filter(Boolean).forEach(d => g.dims.add(d));
    }
    return [...groups.values()].sort((a, b) => a.model.localeCompare(b.model));
  }

  function initialEffort(g) {
    return ['medium', 'high', 'low'].find(e => g.efforts.has(e));
  }

  async function loadModels() {
    const rows = await api('models');
    const groups = groupModels(rows);
    state.models = new Map(groups.map(g => [g.model, g]));
    const root = document.querySelector('#scores');
    if (!groups.length) { root.innerHTML = '<p class="muted">No finished runs yet.</p>'; return; }
    root.innerHTML = groups.map((g, i) => {
      const dims = DIMS.filter(d => g.dims.has(d));
      const efforts = EFFORT_ORDER.filter(e => g.efforts.has(e));
      return `<article class="card" data-model="${esc(g.model)}">
        <div class="card-header"><h2>${esc(g.model)}</h2><span class="muted meta"></span></div>
        <div class="button-row dims">${dims.map(d => button(d, `data-dim="${d}"`)).join('')}</div>
        <div class="button-row efforts">${efforts.map(e => button(e, `data-effort="${e}"`)).join('')}</div>
        <div class="chart"></div></article>`;
    }).join('');
    root.querySelectorAll('.card').forEach(el => {
      const g = state.models.get(el.dataset.model);
      el.dataset.dim = DIMS.find(d => g.dims.has(d));
      el.dataset.effort = initialEffort(g);
      el.querySelectorAll('.dims button').forEach(b => { b.onclick = () => { el.dataset.dim = b.dataset.dim; renderChart(el); }; });
      el.querySelectorAll('.efforts button').forEach(b => { b.onclick = () => { el.dataset.effort = b.dataset.effort; renderChart(el); }; });
    });
    observe(root);
  }

  function observe(root) {
    const io = new IntersectionObserver(entries => entries.forEach(e => {
      if (e.isIntersecting) { io.unobserve(e.target); renderChart(e.target); }
    }), { rootMargin: '300px' });
    root.querySelectorAll('.card').forEach(el => io.observe(el));
  }

  function versionMarks(rows) {
    const marks = [];
    rows.forEach((r, i) => { if (i > 0 && r.dataset_version !== rows[i - 1].dataset_version) marks.push([r.t, r.dataset_version]); });
    return marks;
  }

  async function renderChart(el) {
    const model = el.dataset.model, effort = el.dataset.effort, dim = el.dataset.dim;
    el.querySelectorAll('.dims button').forEach(b => b.setAttribute('aria-selected', b.dataset.dim === dim));
    el.querySelectorAll('.efforts button').forEach(b => b.setAttribute('aria-selected', b.dataset.effort === effort));
    const days = RANGE_DAYS[state.range];
    const from = days ? Math.floor(Date.now() / 1000 - days * 86400) : '';
    const target = el.querySelector('.chart');
    let rows;
    try { rows = await api('series', { model, effort, dim, from }); } catch (e) { target.textContent = 'Unable to load data.'; return; }
    if (el.dataset.effort !== effort || el.dataset.dim !== dim) return;
    target.replaceChildren();
    const last = rows[rows.length - 1];
    el.querySelector('.meta').innerHTML = last
      ? `availability ${num(last.availability * 100, 0)}% · last run ${esc(when(last.t))}`
      : 'no data in range';
    if (!rows.length) { target.innerHTML = '<p class="muted">No data in this range.</p>'; return; }

    const fg = css('--fg'), muted = css('--muted'), accent = css('--accent'), line = css('--line');
    const marks = versionMarks(rows);
    const t0 = rows[0].t, t1 = rows[rows.length - 1].t;
    const pad = t1 === t0 ? 6 * 3600 : (t1 - t0) * 0.03;
    const xMin = t0 - pad, xMax = t1 + pad;
    const data = [rows.map(r => r.t), rows.map(r => r.score), rows.map(r => r.latency_p50)];
    new uPlot({
      width: Math.max(300, target.clientWidth), height: 240,
      cursor: { drag: { x: false, y: false } },
      scales: {
        x: { time: true, auto: false, min: xMin, max: xMax },
        score: { range: [0, 100] },
        latency: { range: (u, min, max) => [0, Math.max((max || 0) * 1.15, 1)] },
      },
      series: [
        {},
        { label: 'Score', scale: 'score', stroke: accent, width: 2, points: { show: rows.length < 60, size: 6, fill: accent } },
        { label: 'Time to solve (s)', scale: 'latency', stroke: muted, width: 2, dash: [6, 4], points: { show: rows.length < 60, size: 5, fill: muted } },
      ],
      axes: [
        { stroke: muted, grid: { stroke: line, width: 1 }, ticks: { stroke: line } },
        { scale: 'score', stroke: muted, grid: { stroke: line, width: 1 }, ticks: { stroke: line } },
        { scale: 'latency', side: 1, stroke: muted, grid: { show: false }, ticks: { stroke: line } },
      ],
      hooks: {
        draw: [u => {
          const ctx = u.ctx;
          ctx.save(); ctx.strokeStyle = fg; ctx.fillStyle = fg; ctx.setLineDash([4, 4]); ctx.font = '11px system-ui';
          for (const [t, v] of marks) {
            const x = Math.round(u.valToPos(t, 'x', true));
            ctx.beginPath(); ctx.moveTo(x, u.bbox.top); ctx.lineTo(x, u.bbox.top + u.bbox.height); ctx.stroke();
            ctx.fillText(v, x + 4, u.bbox.top + 12);
          }
          ctx.restore();
        }],
      },
    }, data, target);
  }

  async function loadCompare() {
    const root = document.querySelector('#compare');
    root.dataset.loaded = '1';
    root.innerHTML = '<p class="muted legend">Bar = score (0–100). Dot = time to solve: request start to end of reply, thinking included, network round trip removed; dot position is relative to the slowest row of the card. Text = score · time · cost per correct answer.</p>' + DIMS.map(d => `<article class="card compare-card"><h2>${esc(d)}</h2><div class="ranking" id="rank-${d}">Loading…</div></article>`).join('');
    await Promise.all(DIMS.map(async d => {
      const box = root.querySelector(`#rank-${d}`);
      try {
        const rows = await api('ranking', { dim: d });
        const max = Math.max(1, ...rows.map(x => x.latency_p50 || 0));
        box.innerHTML = rows.map(x => `<div class="rank-row">
          <span class="rank">${x.rank ?? '—'}</span>
          <span class="name">${esc(x.model)}<span class="muted">@${esc(x.effort)}</span></span>
          <span class="track"><span class="bar" style="width:${x.score == null ? 0 : x.score}%"></span>${x.latency_p50 == null ? '' : `<span class="dot" style="left:${x.latency_p50 / max * 100}%"></span>`}</span>
          <span class="row-value">${num(x.score)} · ${secs(x.latency_p50)} · ${usd(x.cost_per_correct)}</span></div>`).join('') || '<p class="muted">No data.</p>';
      } catch (e) { box.textContent = 'Unable to load data.'; }
    }));
  }

  async function loadFooter() {
    const health = (await api('health'))[0] || {};
    document.querySelector('#last-run').textContent = when(health.last_finished_at);
    try {
      const rows = await api('ranking', { dim: DIMS[0] });
      const versions = [...new Set(rows.map(r => r.dataset_version))];
      document.querySelector('#dataset').textContent = versions.join(', ') || '—';
    } catch (e) { /* footer stays at the placeholder */ }
  }

  document.querySelectorAll('[data-tab]').forEach(b => { b.onclick = () => setTab(b.dataset.tab); });
  document.querySelectorAll('[data-range]').forEach(b => {
    b.setAttribute('aria-selected', b.dataset.range === state.range);
    b.onclick = () => {
      state.range = b.dataset.range;
      document.querySelectorAll('[data-range]').forEach(x => x.setAttribute('aria-selected', x === b));
      loadModels();
    };
  });
  window.addEventListener('hashchange', () => setTab(location.hash.slice(1)));
  (async () => {
    try { await Promise.all([loadFooter(), loadModels()]); }
    catch (e) { document.querySelector('#scores').textContent = 'Unable to load monitor data.'; }
    setTab(location.hash.slice(1));
  })();
})();

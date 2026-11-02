(async () => {
  const root = document.querySelector('#scores');
  function button(label, attrs = '') { return `<button ${attrs}>${esc(label)}</button>`; }
  async function renderChart(el) {
    const { model, effort, dim } = el.dataset;
    el.querySelectorAll('.dims button').forEach(b => b.setAttribute('aria-selected', b.dataset.dim === dim));
    el.querySelectorAll('.efforts button').forEach(b => b.setAttribute('aria-selected', b.dataset.effort === effort));
    const days = RANGE_DAYS[state.range], from = days ? Math.floor(Date.now()/1000 - days*86400) : '';
    const target = el.querySelector('.chart'); let rows;
    try { rows = await api('series', { model, effort, dim, from }); } catch (_) { target.textContent = tr('status.loadSeries'); return; }
    if (el.dataset.effort !== effort || el.dataset.dim !== dim) return;
    target.replaceChildren(); const last = rows.at(-1);
    el.querySelector('.meta').textContent = last ? tr('availability', {n:num(last.availability * 100, 0), date:when(last.t)}) : tr('status.noDataRangeShort');
    if (!rows.length) { target.textContent = tr('status.noDataRange'); return; }
    const ui = dim === 'ui', showQuality = !ui && ['write_zh','write_en'].includes(dim) && rows.some(r => r.quality != null);
    const data = [rows.map(r => r.t), rows.map(r => r.score), ...(ui ? [] : [rows.map(r => r.latency_p50)]), ...(showQuality ? [rows.map(r => r.quality)] : [])];
    const marks = versionMarks(rows), t0 = rows[0].t, t1 = rows.at(-1).t, pad = t1 === t0 ? 21600 : (t1-t0)*.03;
    new uPlot({ width:Math.max(300,target.clientWidth), height:240, scales:{x:{time:true,auto:false,min:t0-pad,max:t1+pad},score:{range:[0,100]},latency:{range:(u,min,max)=>[0,Math.max((max||0)*1.15,1)]}}, series:[{}, {label:tr('chart.score'),scale:'score',stroke:css('--accent'),width:2,points:{show:rows.length<60,size:6}}, ...(ui?[]:[{label:tr('chart.time'),scale:'latency',stroke:css('--muted'),width:2,dash:[6,4]}]), ...(showQuality?[{label:tr('chart.quality'),scale:'score',stroke:css('--fg'),width:2,dash:[2,4]}]:[])], axes:[{}, {scale:'score'}, ...(ui?[]:[{scale:'latency',side:1}])], hooks:{draw:[u=>{const c=u.ctx;c.save();c.strokeStyle=css('--fg');c.setLineDash([4,4]);c.font='11px system-ui';for(const [t,v] of marks){const x=Math.round(u.valToPos(t,'x',true));c.beginPath();c.moveTo(x,u.bbox.top);c.lineTo(x,u.bbox.top+u.bbox.height);c.stroke();c.fillText(v,x+4,u.bbox.top+12);}c.restore();}]}}, data, target);
  }
  async function load() {
    const [dims, rows] = await Promise.all([loadDimensions(), api('models')]);
    const groups = groupModels(rows); if (!groups.length) { root.textContent=tr('status.noFinishedRuns'); return; }
    root.innerHTML = groups.map(g => { const ds=dims.filter(d=>g.dims.has(d.dim)); return `<article class="card" data-model="${esc(g.model)}"><div class="card-header"><h2>${esc(g.model)}</h2><span class="muted meta"></span></div><div class="button-row dims">${ds.map(d=>button(dimName(d),`data-dim="${d.dim}" title="${esc(dimUse(d))}"`)).join('')}</div><div class="button-row efforts">${EFFORT_ORDER.filter(e=>g.efforts.has(e)).map(e=>button(tr(`effort.${e}`),`data-effort="${e}"`)).join('')}</div><div class="chart"></div></article>`; }).join('');
    root.querySelectorAll('.card').forEach(el => { const g=groups.find(x=>x.model===el.dataset.model); el.dataset.dim=dims.find(d=>g.dims.has(d.dim)).dim; el.dataset.effort=initialEffort(g); el.querySelectorAll('.dims button').forEach(b=>b.onclick=()=>{el.dataset.dim=b.dataset.dim;renderChart(el)}); el.querySelectorAll('.efforts button').forEach(b=>b.onclick=()=>{el.dataset.effort=b.dataset.effort;renderChart(el)}); renderChart(el); });
  }
  document.querySelectorAll('[data-range]').forEach(b=>b.onclick=()=>{state.range=b.dataset.range;document.querySelectorAll('[data-range]').forEach(x=>x.setAttribute('aria-selected',x===b));load();});
  try { await Promise.all([loadFooter(),load()]); } catch (_) { root.textContent=tr('status.loadData'); }
  document.addEventListener('langchange', () => load().catch(() => { root.textContent=tr('status.loadData'); }));
})();

const UI_EFFORT_ORDER = { low: 0, medium: 1, high: 2 };
function cardKey(sample) { return `${sample.model}|${sample.effort}|${sample.prompt_key}`; }

function newestSample(rows) {
  return [...rows].sort((a, b) => Number(b.created_at || 0) - Number(a.created_at || 0) || Number(b.sample_id || 0) - Number(a.sample_id || 0))[0];
}

function reduceSamples(rows) {
  const targets = new Map();
  rows.forEach(row => {
    const key = cardKey(row);
    const current = targets.get(key);
    const usable = sample => Boolean(sample.svg && sample.valid);
    if (!current || (usable(row) && !usable(current)) || (usable(row) === usable(current) && newestSample([current, row]) === row)) targets.set(key, row);
  });
  return [...targets.values()].sort((a, b) => a.prompt_key === b.prompt_key
    ? a.model.localeCompare(b.model) || (UI_EFFORT_ORDER[a.effort] ?? 99) - (UI_EFFORT_ORDER[b.effort] ?? 99)
    : a.prompt_key === 'classic' ? -1 : b.prompt_key === 'classic' ? 1 : a.prompt_key.localeCompare(b.prompt_key));
}

function groupSamples(rows, order) {
  const sections = new Map();
  reduceSamples(rows).forEach(sample => {
    if (!sections.has(sample.prompt_key)) sections.set(sample.prompt_key, { promptKey: sample.prompt_key, prompt: sample.prompt, cards: [] });
    sections.get(sample.prompt_key).cards.push(sample);
  });
  const rank = order ? new Map(order.map((id, i) => [id, i])) : null;
  sections.forEach(section => section.cards.sort(rank
    ? (a, b) => (rank.get(cardKey(a)) ?? 1e9) - (rank.get(cardKey(b)) ?? 1e9)
    : (a, b) =>
    (b.stars == null ? -1 : a.stars == null ? 1 : Number(b.stars) - Number(a.stars)) ||
    a.model.localeCompare(b.model) || (UI_EFFORT_ORDER[a.effort] ?? 99) - (UI_EFFORT_ORDER[b.effort] ?? 99)));
  return [...sections.values()].sort((a, b) => a.promptKey === 'classic' ? -1 : b.promptKey === 'classic' ? 1 : a.promptKey.localeCompare(b.promptKey));
}

function historySamples(rows, newest) {
  return rows.filter(row => row.prompt_key === newest.prompt_key && row.svg && row.valid && row.sample_id !== newest.sample_id)
     .sort((a, b) => Number(b.created_at || 0) - Number(a.created_at || 0) || Number(b.sample_id || 0) - Number(a.sample_id || 0)).slice(0, 4);
}

if (typeof window !== 'undefined') Object.assign(window, { reduceSamples, groupSamples, historySamples, cardKey });

if (typeof document !== 'undefined') (async () => {
  const root = document.querySelector('#ui'), form = document.querySelector('#key-form'), msg = document.querySelector('#key-message');
  let key = sessionStorage.getItem('rating-key') || '', samples = [], cache = new Map(), open = new Set(), order = null;
  i18n.add({ en: {
    'ui.classic': 'Classic', 'ui.variant': 'Variant', 'ui.history': 'History', 'ui.noHistory': 'No history yet'
  }, zh: {
    'ui.classic': '经典', 'ui.variant': '变体', 'ui.history': '历史', 'ui.noHistory': '暂无历史'
  }});
  const image = svg => svg ? `<img alt="${tr('ui.svgSample')}" src="data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}">` : `<div class="placeholder">${tr('ui.invalid')}</div>`;
  function stars(sample, historyKey = '') {
    const controls = key && sample.valid && sample.svg ? Array.from({ length: 10 }, (_, i) => `<button type="button" data-star="${i + 1}" aria-label="${tr('ui.starCount', { n: i + 1 })}">${i + 1 <= sample.stars ? '★' : '☆'}</button>`).join('') : sample.stars ? `${'★'.repeat(sample.stars)}${'☆'.repeat(10 - sample.stars)}` : tr('ui.notRated');
    return `<div class="stars" data-history-key="${esc(historyKey)}" aria-label="${sample.stars ? tr('ui.stars', { n: sample.stars }) : tr('ui.notRated')}">${controls}</div>`;
  }
  function renderHistory(sample) {
    const rows = cache.get(cardKey(sample)) || [], older = historySamples(rows, sample), id = esc(cardKey(sample));
     if (!older.length) return `<div class="history-panel" data-for="${id}"><p class="muted">${tr('ui.noHistory')}</p></div>`;
     return `<div class="history-panel" data-for="${id}"><div class="history">${older.map(row => `<article class="sample history-sample" data-id="${row.sample_id}">${image(row.svg)}<p><time datetime="${esc(String(row.created_at || ''))}">${esc(when(row.created_at))}</time></p>${stars(row, cardKey(sample))}</article>`).join('')}</div></div>`;
  }
  function placeHistory() {
    root.querySelectorAll('.history-panel').forEach(panel => {
      const card = [...root.querySelectorAll('.sample')].find(el => el.dataset.cardKey === panel.dataset.for);
      if (card) panel.style.top = `${card.offsetTop + card.offsetHeight + 4}px`;
    });
  }
  function render() {
     root.innerHTML = groupSamples(samples, order).map(section => `<section class="ui-section"><h2 class="ui-section-heading" title="${esc(section.prompt)}"><span class="ui-kind">${esc(tr(`ui.${section.promptKey}`))}</span><span class="ui-subject">${esc(tr(`ui.subject.${section.promptKey}`))}</span></h2><div class="sample-grid">${section.cards.map(sample => { const id = cardKey(sample), shown = open.has(id); return `<article class="sample" data-id="${sample.sample_id}" data-card-key="${esc(id)}">${image(sample.svg && sample.valid ? sample.svg : null)}<p>${esc(sample.model)} · ${esc(sample.effort)}</p>${stars(sample, id)}<button type="button" class="history-toggle" data-history="${esc(id)}" title="${tr('ui.history')}" aria-label="${tr('ui.history')}" aria-expanded="${shown}">◷</button></article>`; }).join('')}${section.cards.filter(sample => open.has(cardKey(sample))).map(sample => renderHistory(sample)).join('')}</div></section>`).join('');
    placeHistory();
    root.querySelectorAll('[data-history]').forEach(button => button.onclick = async () => {
      const id = button.dataset.history, sample = samples.find(row => cardKey(row) === id);
      if (open.has(id)) { open.delete(id); render(); return; }
      if (!cache.has(id)) cache.set(id, await api('ui_samples', { model: sample.model, effort: sample.effort }));
      open.add(id); render();
    });
    document.onkeydown = event => { if (event.key === 'Escape' && open.size) { open.clear(); render(); } };
    document.onclick = event => { if (open.size && !event.target.closest('.history-panel, .history-toggle')) { open.clear(); render(); } };
    root.querySelectorAll('[data-star]').forEach(button => button.onclick = async () => {
      const sample = button.closest('[data-id]'), historyKey = button.closest('.stars').dataset.historyKey, body = new URLSearchParams({ sample_id: sample.dataset.id, stars: button.dataset.star });
      try {
        await api('rate', {}, { method: 'POST', headers: { Authorization: `Bearer ${key}`, Accept: 'application/json', 'Content-Type': 'application/x-www-form-urlencoded' }, body });
        samples = samples.map(row => row.sample_id === Number(sample.dataset.id) ? { ...row, stars: Number(button.dataset.star) } : row);
        if (historyKey) cache.set(historyKey, await api('ui_samples', { model: historyKey.split('|')[0], effort: historyKey.split('|')[1] }));
        else samples = await api('ui_samples');
        render();
      } catch (_) { msg.textContent = tr('ui.notAccepted'); }
    });
  }
  async function load() { samples = await api('ui_samples'); order = groupSamples(samples).flatMap(section => section.cards.map(cardKey)); render(); await loadFooter(); }
  form.onsubmit = async event => { event.preventDefault(); const candidate = document.querySelector('#rating-key').value; try { await api('whoami', {}, { headers: { Authorization: `Bearer ${candidate}` } }); sessionStorage.setItem('rating-key', candidate); key = candidate; msg.textContent = tr('ui.accepted'); render(); } catch (_) { msg.textContent = tr('ui.notAccepted'); } };
  try { await load(); } catch (_) { root.textContent = tr('status.loadData'); }
  document.addEventListener('langchange', () => { msg.textContent = ''; render(); });
  window.addEventListener('resize', placeHistory);
})();

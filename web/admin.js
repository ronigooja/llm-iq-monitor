(function () {
  'use strict';

  const DIMENSIONS = ['reasoning', 'code', 'instruction', 'write_zh', 'write_en', 'ui'];
  const EFFORTS = ['low', 'medium', 'high'];
  const $ = (selector, root) => (root || document).querySelector(selector);
  const $$ = (selector, root) => Array.from((root || document).querySelectorAll(selector));
  const clone = value => JSON.parse(JSON.stringify(value));
  let state = null;
  let original = null;
  let lastStatus = null;
  let statusTimer = null;
  let activeTab = 'settings';
  let dirty = false;
  const STATUS_INTERVAL_MS = 15000;

  function escapeHtml(value) {
    return String(value ?? '').replace(/[&<>"']/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]));
  }

  function getAt(object, path) {
    return path.split('.').reduce((value, key) => value == null ? undefined : value[key], object);
  }
  function setAt(object, path, value) {
    const parts = path.split('.');
    const last = parts.pop();
    const target = parts.reduce((value, key) => value[key] || (value[key] = {}), object);
    target[last] = value;
  }
  function selectedValues(root) {
    return $$('input:checked', root).map(input => input.value);
  }
  function applyFieldInputs(root, inputs) {
    const settings = clone(root);
    inputs.forEach(input => {
      const field = input.dataset.field;
      if (input.type === 'checkbox') { setAt(settings, field, input.checked); return; }
      let value = input.value;
      if (input.type === 'number') value = value === '' ? null : Number(value);
      setAt(settings, field, value);
    });
    return settings;
  }
  function collectSettings(root) {
    const settings = applyFieldInputs(root, $$('[data-field]'));
    settings.models.default_dims = selectedValues($('#default-dims'));
    settings.models.default_efforts = selectedValues($('#default-efforts'));
    $$('#models-table tbody tr[data-model]').forEach(row => {
      const id = row.dataset.model;
      const configured = settings.models.per_model[id] || {};
      configured.enabled = Boolean($('.model-enabled', row).checked);
      configured.interval_h = Number($('.model-interval', row).value);
      configured.dims = selectedValues($('.model-dims', row));
      configured.efforts = selectedValues($('.model-efforts', row));
      settings.models.per_model[id] = configured;
    });
    return settings;
  }
  function bulkApply(settings, modelIds, values) {
    const next = clone(settings);
    modelIds.forEach(id => {
      const item = next.models.per_model[id] || {};
      item.interval_h = Number(values.interval_h);
      item.dims = values.dims.slice();
      item.efforts = values.efforts.slice();
      item.enabled = true;
      next.models.per_model[id] = item;
    });
    return next;
  }
  function bulkValues(intervalRaw, dims, efforts) {
    const interval = Number(intervalRaw);
    if (String(intervalRaw).trim() === '' || !Number.isInteger(interval) || interval < 1) return { error: 'bulkInterval' };
    if (!dims.length) return { error: 'bulkDims' };
    if (!efforts.length) return { error: 'bulkEfforts' };
    return { values: { interval_h: interval, dims, efforts } };
  }
  function errorFields(errors) {
    return (errors || []).reduce((result, error) => {
      if (error && error.field) result[error.field] = error.message || '';
      return result;
    }, {});
  }
  function formatCount(value) {
    if (value == null || Number.isNaN(Number(value))) return '—';
    const n = Number(value);
    const trim = x => x.toFixed(1).replace(/\.0$/, '');
    if (Math.abs(n) >= 1e6) return `${trim(n / 1e6)}M`;
    if (Math.abs(n) >= 1e3) return `${trim(n / 1e3)}K`;
    return String(Math.round(n));
  }
  function weekly(value) { return value == null ? null : Number(value) * 7; }
  function formatPrice(value) {
    if (value == null) return '—';
    return `$${Number(value).toFixed(2).replace(/\.?0+$/, '')}`;
  }
  function formatModelPrice(model) {
    return model.price_in == null || model.price_out == null ? '—' : `${formatPrice(model.price_in)} / ${formatPrice(model.price_out)}`;
  }
  function formatTime(seconds, locale) {
    return seconds == null ? '—' : new Date(Number(seconds) * 1000).toLocaleString(locale);
  }
  function statusCells(entry, t, locale) {
    const run = entry.run;
    const kind = run ? 'running' : entry.deferred ? 'deferred' : entry.next_due_at != null ? 'waiting' : 'idle';
    const labels = { running: 'statusRunning', deferred: 'statusDeferred', waiting: 'statusWaiting', idle: 'statusIdle' };
    const status = {
      kind,
      label: t(labels[kind], run ? { n: run.question_index, total: run.question_total } : {}),
      progress: run ? { value: run.question_index, max: run.question_total } : null
    };
    const last = entry.last_run ? `${entry.last_run.status} · ${formatTime(entry.last_run.finished_at, locale)}` : '—';
    const next = formatTime(entry.next_due_at, locale);
    if (!entry.probe) return { status, last, next, probe: { state: 'none', label: '—', detail: '—' } };
    const probe = entry.probe;
    const state = ['busy', 'idle', 'unknown'].includes(probe.state) ? probe.state : 'unknown';
    const parts = [];
    if (probe.last_ok != null) parts.push(t(probe.last_ok ? 'probeOk' : 'probeFail'));
    if (probe.last_latency_s != null) parts.push(t('probeLatency', { s: Number(probe.last_latency_s).toFixed(1) }));
    if (probe.availability != null) parts.push(t('probeDetail', { pct: `${(Number(probe.availability) * 100).toFixed(1)}%`, n: probe.samples }));
    return { status, last, next, probe: { state, label: t(`state${state[0].toUpperCase()}${state.slice(1)}`), detail: parts.join(' · ') || '—' } };
  }
  window.adminHelpers = { collectSettings, applyFieldInputs, bulkApply, bulkValues, errorFields, formatCount, weekly, formatPrice, formatModelPrice, statusCells };
  if (typeof document.addEventListener !== 'function') return;

  function tr(key, vars) { return window.i18n.t(`admin.${key}`, vars); }
  function request(url, options) {
    const init = Object.assign({}, options || {});
    if ((init.method || 'GET').toUpperCase() !== 'GET') {
      init.headers = Object.assign({}, init.headers || {}, { 'X-Admin': '1' });
    }
    return fetch(url, init).then(async response => {
      let body = null;
      try { body = await response.json(); } catch (error) { /* empty response */ }
      if (!response.ok) { const failure = new Error(body && body.error || response.statusText); failure.status = response.status; failure.body = body; failure.retryAfter = response.headers.get('Retry-After'); throw failure; }
      return body;
    });
  }
  function jsonRequest(url, method, body) {
    return request(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(body) });
  }
  function showLogin(show) {
    $('#login-view').hidden = !show;
    $('#console-view').hidden = show;
    dirty = false;
    $('#save-bar').hidden = true;
    $('#logout').hidden = show;
    if (show) selectTab('settings');
  }
  function setMessage(selector, text) { $(selector).textContent = text || ''; }
  function optionCheckboxes(container, values, selected, prefix) {
    container.innerHTML = values.map(value => `<label><input type="checkbox" value="${value}"${selected.includes(value) ? ' checked' : ''}><span>${prefix === 'effort' ? value : window.i18n.t(`dim.${value}.name`)}</span></label>`).join('');
  }
  function fieldValue(path) { return getAt(state.settings, path); }
  function populateField(path) {
    const input = $(`[data-field="${path}"]`);
    if (!input) return;
    if (input.type === 'checkbox') input.checked = Boolean(fieldValue(path));
    else input.value = fieldValue(path) == null ? '' : fieldValue(path);
  }
  function renderSettings() {
    ['gateway.base_url', 'gateway.models_url', 'schedule.heartbeat_cron', 'schedule.defer_when_busy', 'models.default_interval_h', 'run.parallel_models', 'run.timeout_s', 'run.max_tokens', 'run.max_attempts', 'run.retry_delay_s', 'net.rtt_fallback_ms', 'retention.reply_days', 'availability.enabled', 'availability.probe_effort', 'availability.probe_timeout_s', 'availability.probe_idle_every_min', 'availability.probe_busy_every_min', 'availability.classify_every_min', 'availability.state_window_min', 'availability.busy_fail_rate', 'availability.busy_latency_factor', 'availability.window_min', 'availability.min_samples', 'availability.retention_days'].forEach(populateField);
    optionCheckboxes($('#default-dims'), DIMENSIONS, state.settings.models.default_dims || DIMENSIONS);
    optionCheckboxes($('#default-efforts'), EFFORTS, state.settings.models.default_efforts || ['medium'], 'effort');
    $('#heartbeat-next').textContent = (state.heartbeat_next || []).join(' · ') || '—';
    $('#runs-per-week').textContent = window.adminHelpers.formatCount(window.adminHelpers.weekly(state.budget && state.budget.runs_per_day));
    $('#tokens-per-week').textContent = window.adminHelpers.formatCount(window.adminHelpers.weekly(state.budget && state.budget.tokens_per_day));
    $('#key-status').textContent = state.key_set ? tr('keySet') : tr('keyNotSet');
    const priced = (state.models || []).filter(model => model.priced);
    const judge = $('[data-field="judge.model"]');
    judge.innerHTML = priced.map(model => `<option value="${model.id}">${model.id}</option>`).join('');
    judge.value = state.settings.judge.model;
    const judgeEffort = $('[data-field="judge.effort"]');
    judgeEffort.innerHTML = EFFORTS.map(effort => `<option value="${effort}">${effort}</option>`).join('');
    judgeEffort.value = state.settings.judge.effort;
    renderModels();
  }
  function modelSettings(model) {
    return state.settings.models.per_model[model.id] || {};
  }
  function renderModels() {
    const query = ($('#model-search').value || '').toLowerCase();
    const showUnpriced = $('#show-unpriced').checked;
    const unpricedCount = (state.models || []).filter(model => !model.priced).length;
    $('#show-unpriced-label').textContent = tr('showUnpriced', { n: unpricedCount });
    const tbody = $('#models-table tbody');
    tbody.innerHTML = '';
    (state.models || []).filter(model => model.id.toLowerCase().includes(query) && (showUnpriced || model.priced)).forEach(model => {
      const settings = modelSettings(model);
      const dims = settings.dims || state.settings.models.default_dims || DIMENSIONS;
      const efforts = settings.efforts || state.settings.models.default_efforts || ['medium'];
      const row = document.createElement('tr');
      row.dataset.model = model.id;
      if (!model.priced) row.className = 'no-price';
       row.innerHTML = `<td><input class="model-select" type="checkbox" value="${model.id}"${model.priced ? '' : ' disabled'}></td><td class="model-id">${model.id}</td><td class="model-price">${formatModelPrice(model)}</td><td><input class="model-enabled" type="checkbox"${settings.enabled ? ' checked' : ''}${model.priced ? '' : ' disabled'}></td><td><input class="model-interval" type="number" min="1" value="${settings.interval_h || state.settings.models.default_interval_h}"></td><td><div class="model-dims compact-checks"></div></td><td><div class="model-efforts compact-checks"></div></td>`;
      optionCheckboxes($('.model-dims', row), state.dims || DIMENSIONS, dims);
      optionCheckboxes($('.model-efforts', row), state.efforts || EFFORTS, efforts, 'effort');
      tbody.appendChild(row);
    });
    const selectable = $$('.model-select:not(:disabled)');
    const selected = selectable.filter(input => input.checked).length;
    const selectAll = $('#select-all-models');
    selectAll.checked = selectable.length > 0 && selected === selectable.length;
    selectAll.indeterminate = selected > 0 && selected < selectable.length;
    updateBulkBar();
  }
  function updateBulkBar() {
    const count = $$('.model-select:checked').length;
    $('#bulk-bar').hidden = count === 0;
    $('#selected-count').textContent = tr('selected', { n: count });
  }
  function markDirty() { dirty = true; $('#save-bar').hidden = activeTab !== 'settings'; setMessage('#save-message', ''); }
  function selectTab(tab) {
    activeTab = tab === 'status' ? 'status' : 'settings';
    $$('#admin-tabs [data-tab]').forEach(button => button.setAttribute('aria-selected', String(button.dataset.tab === activeTab)));
    $('#settings-pane').hidden = activeTab !== 'settings';
    $('#status-pane').hidden = activeTab !== 'status';
    $('#save-bar').hidden = activeTab !== 'settings' || !dirty;
    if (activeTab === 'status' && state) refreshStatus();
  }
  function clearErrors() { $$('.field-error').forEach(node => node.remove()); $('#validation-summary').hidden = true; }
  function showErrors(errors) {
    clearErrors();
    const mapped = window.adminHelpers.errorFields(errors);
    const summary = $('#validation-summary'); summary.textContent = tr('saveSummary'); summary.hidden = false;
    Object.keys(mapped).forEach(field => {
      const input = $(`[data-field="${field}"]`);
      if (!input) return;
      const error = document.createElement('span'); error.className = 'field-error'; error.textContent = mapped[field]; input.insertAdjacentElement('afterend', error);
    });
  }
  function renderStatus() {
    const body = $('#status-table tbody');
    if (!lastStatus) { body.innerHTML = `<tr><td colspan="6" class="muted">${escapeHtml(tr('statusFailed'))}</td></tr>`; return; }
    $('#runner-stopped').hidden = !(lastStatus.runner && lastStatus.runner.running === false);
    const models = lastStatus.models || [];
    if (!models.length) { body.innerHTML = `<tr><td colspan="6" class="muted">${escapeHtml(tr('statusEmpty'))}</td></tr>`; return; }
    const locale = window.i18n.lang() === 'zh' ? 'zh-CN' : 'en';
    body.innerHTML = models.map(entry => {
      const cells = window.adminHelpers.statusCells(entry, tr, locale);
      const bar = cells.status.progress ? `<progress max="${cells.status.progress.max}" value="${cells.status.progress.value}"></progress>` : '';
      return `<tr><th scope="row">${escapeHtml(entry.model)}</th><td>${escapeHtml(entry.effort)}</td><td><span class="status-chip status-${cells.status.kind}">${escapeHtml(cells.status.label)}</span>${bar}</td><td>${escapeHtml(cells.last)}</td><td>${escapeHtml(cells.next)}</td><td><span class="probe-chip probe-${cells.probe.state}">${escapeHtml(cells.probe.label)}</span> <span class="muted">${escapeHtml(cells.probe.detail)}</span></td></tr>`;
    }).join('');
  }
  function refreshStatus() {
    return request('/admin/api/status').then(next => {
      lastStatus = next;
      renderStatus();
      setMessage('#status-updated', tr('statusUpdated', { time: new Date().toLocaleTimeString(window.i18n.lang() === 'zh' ? 'zh-CN' : 'en') }));
    }).catch(error => {
      if (error.status === 401) { showLogin(true); setMessage('#login-message', tr('unauthorized')); return; }
      lastStatus = null;
      renderStatus();
    });
  }
  function startStatusPolling() {
    if (statusTimer) return;
    statusTimer = setInterval(() => { if (!document.hidden && state && activeTab === 'status') refreshStatus(); }, STATUS_INTERVAL_MS);
  }
  function loadState() {
    setMessage('#load-message', tr('loading'));
    return request('/admin/api/state').then(next => { state = next; original = clone(next); renderSettings(); showLogin(false); setMessage('#load-message', ''); startStatusPolling(); if (activeTab === 'status') refreshStatus(); }).catch(error => {
      if (error.status === 401) { showLogin(true); setMessage('#load-message', tr('unauthorized')); } else setMessage('#load-message', tr('loadFailed'));
    });
  }
  function login(event) {
    event.preventDefault();
    const token = $('#admin-token').value;
    jsonRequest('/admin/api/login', 'POST', { token }).then(() => { $('#admin-token').value = ''; loadState(); }).catch(error => {
      const minutes = error.retryAfter ? Math.ceil(Number(error.retryAfter) / 60) : null;
      setMessage('#login-message', error.status === 429 ? tr('locked', { n: minutes || 1 }) : tr('unauthorized'));
    });
  }
  function logout() { jsonRequest('/admin/api/logout', 'POST', {}).finally(() => { state = null; original = null; showLogin(true); setMessage('#login-message', tr('loggedOut')); }); }
  function save() {
    clearErrors();
    const settings = collectSettings(state.settings);
    const key = $('#gateway-key').value;
    const keyRequest = key ? jsonRequest('/admin/api/key', 'PUT', { key }) : Promise.resolve(null);
    keyRequest.then(() => jsonRequest('/admin/api/settings', 'PUT', settings)).then(next => { $('#gateway-key').value = ''; state = next; original = clone(next); renderSettings(); dirty = false; $('#save-bar').hidden = true; setMessage('#save-message', tr('saved')); }).catch(error => { if (error.status === 401) { showLogin(true); setMessage('#login-message', tr('unauthorized')); } else if (error.status === 422) showErrors(error.body && error.body.errors); else setMessage('#save-message', tr('saveFailed')); });
  }
  function discard() { state = clone(original); renderSettings(); clearErrors(); dirty = false; $('#save-bar').hidden = true; setMessage('#save-message', tr('discarded')); }
  function testConnection() { setMessage('#connection-result', tr('testing')); jsonRequest('/admin/api/test', 'POST', {}).then(result => { setMessage('#connection-result', result.ok ? tr('connectionOk', { status: result.status, models: result.models }) : tr('connectionFailed', { message: result.error || tr('invalid') })); }).catch(error => setMessage('#connection-result', tr('connectionFailed', { message: error.message }))); }
  function refreshModels() { const button = $('#refresh-models'); button.disabled = true; button.textContent = tr('refreshing'); jsonRequest('/admin/api/models/refresh', 'POST', {}).then(next => { state = next; original = clone(next); renderSettings(); }).catch(error => { if (error.status === 401) showLogin(true); }).finally(() => { button.disabled = false; button.textContent = tr('refresh'); }); }
  function resetBulk() {
    $('#bulk-interval').value = '';
    optionCheckboxes($('#bulk-dims'), DIMENSIONS, []);
    optionCheckboxes($('#bulk-efforts'), EFFORTS, [], 'effort');
    updateBulkBar();
  }
  function applyBulk() {
    const ids = $$('.model-select:checked').map(input => input.value);
    const checked = window.adminHelpers.bulkValues($('#bulk-interval').value, selectedValues($('#bulk-dims')), selectedValues($('#bulk-efforts')));
    if (checked.error) { setMessage('#bulk-message', tr(checked.error + 'Invalid')); return; }
    setMessage('#bulk-message', '');
    state.settings = window.adminHelpers.bulkApply(window.adminHelpers.collectSettings(state.settings), ids, checked.values);
    renderModels();
    resetBulk();
    markDirty();
  }
  document.addEventListener('langchange', () => { if (state) renderSettings(); if (state) renderStatus(); window.i18n.apply(); });
  document.addEventListener('visibilitychange', () => { if (!document.hidden && state && activeTab === 'status') refreshStatus(); });
  $('#admin-tabs').addEventListener('click', event => { const button = event.target.closest('[data-tab]'); if (button) selectTab(button.dataset.tab); });
  $('#refresh-status').addEventListener('click', refreshStatus);
  $('#login-form').addEventListener('submit', login);
  $('#logout').addEventListener('click', logout);
  $('#save').addEventListener('click', save);
  $('#discard').addEventListener('click', discard);
  $('#test-connection').addEventListener('click', testConnection);
  $('#refresh-models').addEventListener('click', refreshModels);
  $('#model-search').addEventListener('input', renderModels);
  $('#show-unpriced').addEventListener('change', renderModels);
  $('#select-all-models').addEventListener('change', event => {
    $$('.model-select:not(:disabled)').forEach(input => { input.checked = event.target.checked; });
    updateBulkBar();
    markDirty();
  });
  $('#models-table').addEventListener('change', event => { if (event.target.classList.contains('model-select')) updateBulkBar(); markDirty(); });
  $('#bulk-apply').addEventListener('click', applyBulk);
  $('#console-view').addEventListener('input', event => { if (event.target.matches('input,select')) markDirty(); });
  resetBulk();
  window.i18n.apply();
  loadState();
}());

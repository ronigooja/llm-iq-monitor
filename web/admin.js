(function () {
  'use strict';

  const DIMENSIONS = ['reasoning', 'code', 'instruction', 'write_zh', 'write_en', 'ui'];
  const EFFORTS = ['low', 'medium', 'high'];
  const $ = (selector, root) => (root || document).querySelector(selector);
  const $$ = (selector, root) => Array.from((root || document).querySelectorAll(selector));
  const clone = value => JSON.parse(JSON.stringify(value));
  let state = null;
  let original = null;

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
  function collectSettings(root) {
    const settings = clone(root);
    $$('[data-field]').forEach(input => {
      const field = input.dataset.field;
      if (input.type === 'checkbox') return;
      let value = input.value;
      if (input.type === 'number') value = value === '' ? null : Number(value);
      setAt(settings, field, value);
    });
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
      next.models.per_model[id] = item;
    });
    return next;
  }
  function errorFields(errors) {
    return (errors || []).reduce((result, error) => {
      if (error && error.field) result[error.field] = error.message || '';
      return result;
    }, {});
  }
  function formatPrice(value) {
    if (value == null) return '—';
    return `$${Number(value).toFixed(2).replace(/\.?0+$/, '')}`;
  }
  function formatModelPrice(model) {
    return model.price_in == null || model.price_out == null ? '—' : `${formatPrice(model.price_in)} / ${formatPrice(model.price_out)}`;
  }
  window.adminHelpers = { collectSettings, bulkApply, errorFields, formatPrice, formatModelPrice };
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
    $('#save-bar').hidden = true;
    $('#logout').hidden = show;
  }
  function setMessage(selector, text) { $(selector).textContent = text || ''; }
  function optionCheckboxes(container, values, selected, prefix) {
    container.innerHTML = values.map(value => `<label><input type="checkbox" value="${value}"${selected.includes(value) ? ' checked' : ''}><span>${prefix === 'effort' ? value : window.i18n.t(`dim.${value}.name`)}</span></label>`).join('');
  }
  function fieldValue(path) { return getAt(state.settings, path); }
  function populateField(path) {
    const input = $(`[data-field="${path}"]`);
    if (input) input.value = fieldValue(path) == null ? '' : fieldValue(path);
  }
  function renderSettings() {
    ['gateway.base_url', 'gateway.models_url', 'schedule.heartbeat_cron', 'models.default_interval_h', 'run.parallel_models', 'run.timeout_s', 'run.max_tokens', 'net.rtt_fallback_ms', 'retention.reply_days'].forEach(populateField);
    optionCheckboxes($('#default-dims'), DIMENSIONS, state.settings.models.default_dims || DIMENSIONS);
    optionCheckboxes($('#default-efforts'), EFFORTS, state.settings.models.default_efforts || ['medium'], 'effort');
    $('#heartbeat-next').textContent = (state.heartbeat_next || []).join(' · ') || '—';
    $('#runs-per-day').textContent = state.budget && state.budget.runs_per_day != null ? state.budget.runs_per_day : '—';
    $('#tokens-per-day').textContent = state.budget && state.budget.tokens_per_day != null ? state.budget.tokens_per_day : '—';
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
  function markDirty() { $('#save-bar').hidden = false; setMessage('#save-message', ''); }
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
  function loadState() {
    setMessage('#load-message', tr('loading'));
    return request('/admin/api/state').then(next => { state = next; original = clone(next); renderSettings(); showLogin(false); setMessage('#load-message', ''); }).catch(error => {
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
    keyRequest.then(() => jsonRequest('/admin/api/settings', 'PUT', settings)).then(next => { $('#gateway-key').value = ''; state = next; original = clone(next); renderSettings(); setMessage('#save-message', tr('saved')); }).catch(error => { if (error.status === 401) { showLogin(true); setMessage('#login-message', tr('unauthorized')); } else if (error.status === 422) showErrors(error.body && error.body.errors); else setMessage('#save-message', tr('saveFailed')); });
  }
  function discard() { state = clone(original); renderSettings(); clearErrors(); setMessage('#save-message', tr('discarded')); }
  function testConnection() { setMessage('#connection-result', tr('testing')); jsonRequest('/admin/api/test', 'POST', {}).then(result => { setMessage('#connection-result', result.ok ? tr('connectionOk', { status: result.status, models: result.models }) : tr('connectionFailed', { message: result.error || tr('invalid') })); }).catch(error => setMessage('#connection-result', tr('connectionFailed', { message: error.message }))); }
  function refreshModels() { const button = $('#refresh-models'); button.disabled = true; button.textContent = tr('refreshing'); jsonRequest('/admin/api/models/refresh', 'POST', {}).then(next => { state = next; original = clone(next); renderSettings(); }).catch(error => { if (error.status === 401) showLogin(true); }).finally(() => { button.disabled = false; button.textContent = tr('refresh'); }); }
  function applyBulk() { const ids = $$('.model-select:checked').map(input => input.value); const dims = selectedValues($('#bulk-dims')); const efforts = selectedValues($('#bulk-efforts')); state.settings = window.adminHelpers.bulkApply(state.settings, ids, { interval_h: $('#bulk-interval').value, dims, efforts }); renderModels(); markDirty(); }
  document.addEventListener('langchange', () => { if (state) renderSettings(); window.i18n.apply(); });
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
  optionCheckboxes($('#bulk-dims'), DIMENSIONS, DIMENSIONS);
  optionCheckboxes($('#bulk-efforts'), EFFORTS, ['medium'], 'effort');
  window.i18n.apply();
  loadState();
}());

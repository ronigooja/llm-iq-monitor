import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
HTML = (ROOT / "web/admin.html").read_text(encoding="utf-8")
JS = (ROOT / "web/admin.js").read_text(encoding="utf-8")

AVAILABILITY_FIELDS = [
    "availability.enabled",
    "availability.probe_effort",
    "availability.probe_timeout_s",
    "availability.probe_idle_every_min",
    "availability.probe_busy_every_min",
    "availability.classify_every_min",
    "availability.state_window_min",
    "availability.busy_fail_rate",
    "availability.busy_latency_factor",
    "availability.window_min",
    "availability.min_samples",
    "availability.retention_days",
]


def _node(script):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _helpers_harness():
    return f"""
const fs = require('fs'), vm = require('vm');
const context = {{ window: {{}}, document: {{ querySelector: () => null, querySelectorAll: () => [] }}, fetch: () => {{}} }};
vm.createContext(context);
vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / 'web/admin.js'))}, 'utf8'), context);
const h = context.window.adminHelpers;
const t = (key, vars) => key + (vars ? JSON.stringify(vars) : '');
"""


def test_admin_html_has_every_availability_field_once_with_hint_and_order():
    fields = re.findall(r'data-field="(availability\.[a-z_.]+)"', HTML)
    assert fields == AVAILABILITY_FIELDS
    assert 'data-field="schedule.defer_when_busy" type="checkbox"' in HTML
    assert HTML.index('data-field="availability.enabled"') > HTML.index('id="limits-heading"')
    assert HTML.index('data-field="availability.enabled"') < HTML.index('id="judge-heading"')
    for field in AVAILABILITY_FIELDS + ["schedule.defer_when_busy"]:
        after = HTML.split(f'data-field="{field}"', 1)[1]
        field_block = after.split('data-field=', 1)[0]
        assert re.search(r'<small class="admin-hint" data-i18n="admin\.[^"]+">', field_block) or field == "schedule.defer_when_busy", field


def test_admin_html_status_panel_is_its_own_tab_after_the_settings_pane():
    assert HTML.index('id="settings-pane"') < HTML.index('id="status-pane"')
    settings_pane, status_pane = HTML.split('id="status-pane"', 1)
    assert 'id="status-heading"' not in settings_pane and 'id="status-heading"' in status_pane
    assert 'id="models-heading"' in settings_pane and 'id="overview-heading"' in settings_pane
    assert 'data-tab="settings"' in HTML and 'data-tab="status"' in HTML
    assert 'id="refresh-status"' in HTML and 'id="runner-stopped"' in HTML and 'id="status-table"' in HTML
    assert len(re.findall(r"<h1\b", HTML)) == 1


def test_collect_settings_reads_checkboxes_selects_and_numbers_generically():
    script = _helpers_harness() + """
const original = { schedule: { defer_when_busy: false }, availability: { enabled: false, probe_effort: 'low', busy_fail_rate: 0.5, min_samples: 3 } };
const inputs = [
  { dataset: { field: 'schedule.defer_when_busy' }, type: 'checkbox', checked: true, value: 'on' },
  { dataset: { field: 'availability.enabled' }, type: 'checkbox', checked: true, value: 'on' },
  { dataset: { field: 'availability.probe_effort' }, type: 'select-one', value: 'high' },
  { dataset: { field: 'availability.busy_fail_rate' }, type: 'number', value: '0.25' },
  { dataset: { field: 'availability.min_samples' }, type: 'number', value: '' }
];
const collected = h.applyFieldInputs(original, inputs);
console.log(JSON.stringify({ defer: collected.schedule.defer_when_busy, enabled: collected.availability.enabled, effort: collected.availability.probe_effort, rate: collected.availability.busy_fail_rate, samples: collected.availability.min_samples, original: original.availability.enabled }));
"""
    assert _node(script) == {"defer": True, "enabled": True, "effort": "high", "rate": 0.25, "samples": None, "original": False}


def test_status_cells_format_running_deferred_waiting_idle_and_probe():
    script = _helpers_harness() + """
const run = h.statusCells({ model: 'a', effort: 'low', run: { state: 'running', question_index: 7, question_total: 62, dim: 'code', run_id: 1, started_at: 1 }, last_run: { run_id: 1, status: 'ok', finished_at: 1767225600, score_avg: 0.9 }, next_due_at: null, deferred: false, probe: { state: 'busy', last_probe_at: 1767225600, last_ok: false, last_latency_s: 2.345, availability: 0.5, samples: 12 } }, t, 'en');
const deferred = h.statusCells({ model: 'b', effort: 'low', run: null, last_run: null, next_due_at: 1767229200, deferred: true, probe: null }, t, 'en');
const waiting = h.statusCells({ model: 'c', effort: 'low', run: null, last_run: null, next_due_at: 1767229200, deferred: false, probe: { state: 'idle', last_probe_at: null, last_ok: true, last_latency_s: null, availability: null, samples: 0 } }, t, 'en');
const idle = h.statusCells({ model: 'd', effort: 'low', run: null, last_run: null, next_due_at: null, deferred: false, probe: { state: 'weird', last_probe_at: null, last_ok: null, last_latency_s: null, availability: null, samples: 0 } }, t, 'en');
console.log(JSON.stringify({
  running: { kind: run.status.kind, label: run.status.label, progress: run.status.progress, probe: run.probe.state, detail: run.probe.detail },
  deferred: { kind: deferred.status.kind, probe: deferred.probe.state },
  waiting: { kind: waiting.status.kind, probeDetail: waiting.probe.detail },
  idle: { kind: idle.status.kind, probe: idle.probe.state, next: idle.next }
}));
"""
    result = _node(script)
    assert result["running"]["kind"] == "running"
    assert result["running"]["label"] == 'statusRunning{"n":7,"total":62}'
    assert result["running"]["progress"] == {"value": 7, "max": 62}
    assert result["running"]["probe"] == "busy"
    assert result["running"]["detail"] == 'probeFail · probeLatency{"s":"2.3"} · probeDetail{"pct":"50.0%","n":12}'
    assert result["deferred"] == {"kind": "deferred", "probe": "none"}
    assert result["waiting"]["kind"] == "waiting"
    assert result["waiting"]["probeDetail"] == "probeOk"
    assert result["idle"] == {"kind": "idle", "probe": "unknown", "next": "—"}


def test_status_cells_handle_missing_probe_and_last_run_as_dash():
    script = _helpers_harness() + """
const cells = h.statusCells({ model: 'x', effort: 'high', run: null, last_run: null, next_due_at: null, deferred: false, probe: null }, t, 'en');
console.log(JSON.stringify({ last: cells.last, next: cells.next, probe: cells.probe.label, detail: cells.probe.detail }));
"""
    assert _node(script) == {"last": "—", "next": "—", "probe": "—", "detail": "—"}


def test_admin_status_polling_is_visible_only_and_fifteen_seconds():
    assert "STATUS_INTERVAL_MS = 15000" in JS
    assert "if (!document.hidden && state && activeTab === 'status') refreshStatus()" in JS
    assert "visibilitychange" in JS
    assert "'/admin/api/status'" in JS
    assert "escapeHtml" in JS
    assert "'X-Admin'" in JS and "toUpperCase() !== 'GET'" in JS

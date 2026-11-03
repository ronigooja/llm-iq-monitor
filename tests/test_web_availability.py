import json
import re
import subprocess
from pathlib import Path

import pytest
import yaml
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient

from fixtures import monitor_db  # noqa: F401


ROOT = Path(__file__).parents[1]
PAGE = ROOT / "deploy/templates/pages/availability.html"
SCRIPT = ROOT / "web/availability.js"


def _node(script):
    result = subprocess.run(["node", "-e", script], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def _harness(source_path):
    return f"""
const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync({json.dumps(str(source_path))}, 'utf8');
const context = {{ window: {{}}, document: undefined, localStorage: {{ getItem: () => null }}, navigator: {{ language: 'en' }}, location: {{ pathname: '/availability' }} }};
vm.runInNewContext(source, context);
const h = context.window.availabilityHelpers;
"""


def test_availability_bucket_levels_use_fixed_scale():
    result = _node(_harness(SCRIPT) + """
const levels = [1, 0.99, 0.97, 0.92, 0.8, 0.5, 0, null, undefined, NaN].map(h.avLevel);
console.log(JSON.stringify(levels));
""")
    assert result == ["good", "good", "ok", "warn", "low", "bad", "bad", "none", "none", "none"]


def test_availability_percent_and_null_dash():
    result = _node(_harness(SCRIPT) + """
console.log(JSON.stringify([h.avPercent(0.9876), h.avPercent(null), h.avPercent(1), h.avPercent(0)]));
""")
    assert result == ["98.8%", "—", "100.0%", "0.0%"]


def test_availability_rows_sort_by_model_then_effort_order():
    result = _node(_harness(SCRIPT) + """
const rows = [
  { model: 'zeta', effort: 'low' }, { model: 'alpha', effort: 'high' },
  { model: 'alpha', effort: 'low' }, { model: 'alpha', effort: 'medium' }
];
console.log(JSON.stringify(h.avSortRows(rows).map(r => `${r.model}@${r.effort}`)));
""")
    assert result == ["alpha@low", "alpha@medium", "alpha@high", "zeta@low"]


def test_availability_state_falls_back_to_unknown():
    result = _node(_harness(SCRIPT) + """
console.log(JSON.stringify(['busy', 'idle', 'unknown', 'weird', null].map(h.avState)));
""")
    assert result == ["busy", "idle", "unknown", "unknown", "unknown"]


def test_availability_hourly_and_daily_labels_are_local_time_strings():
    result = _node(_harness(SCRIPT) + """
const hourly = h.avBucketLabel(1767225600, true, 'en');
const daily = h.avBucketLabel(1767225600, false, 'en');
console.log(JSON.stringify({ hourly: hourly.length > 0 && hourly.includes(':'), daily: daily.includes('/') || daily.length > 0 }));
""")
    assert result == {"hourly": True, "daily": True}


def test_limiter_never_runs_more_than_four_tasks_at_once():
    result = _node(_harness(SCRIPT) + """
const gate = h.avLimiter(4);
let active = 0, peak = 0;
const task = () => gate.run(async () => { active += 1; peak = Math.max(peak, active); await new Promise(r => setImmediate(r)); active -= 1; return 1; });
Promise.all(Array.from({ length: 20 }, task)).then(values => console.log(JSON.stringify({ peak, total: values.reduce((a, b) => a + b, 0) })));
""")
    assert result == {"peak": 4, "total": 20}


def test_availability_page_registers_script_strings_and_static_text():
    html = PAGE.read_text(encoding="utf-8")
    script = SCRIPT.read_text(encoding="utf-8")
    assert 'src="/static/availability.js?v=' in html
    assert 'data-av-range="1d"' in html and 'data-av-range="7d"' in html and 'data-av-range="30d"' in html
    assert 'aria-selected="true" data-i18n="av.range1d"' in html
    assert "availability_now" in script and "availability_history" in script
    assert "_shape" not in script.replace("_shape: 'array'", "")
    assert "<script" not in re.sub(r"<script src=[^>]+></script>", "", html)


def test_availability_page_uses_no_inline_style_or_script():
    html = PAGE.read_text(encoding="utf-8")
    assert not re.search(r"\sstyle\s*=", html)
    assert not re.search(r"<script(?![^>]+\bsrc=)[^>]*>", html)
    assert "Content-Security-Policy" in html


def test_availability_script_fetches_history_once_per_row_and_range():
    script = SCRIPT.read_text(encoding="utf-8")
    assert "histories.has(key)" in script
    assert "AV_CONCURRENCY" in script and "avLimiter(AV_CONCURRENCY)" in script
    assert "const AV_CONCURRENCY = 4;" in script


@pytest.mark.asyncio
async def test_availability_page_is_served_with_nav(monitor_db):
    ds = Datasette(
        [str(monitor_db)],
        metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()),
        template_dir=str(ROOT / "deploy/templates"),
        settings={"default_allow_sql": False, "allow_download": False},
    )
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as c:
        response = await c.get("/availability")
    assert response.status_code == 200, response.text
    assert 'aria-current="page" data-i18n="nav.availability"' in response.text
    assert "<title>可用性 Availability · LLM IQ Monitor</title>" in response.text

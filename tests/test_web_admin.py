import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
HTML = (ROOT / "web/admin.html").read_text(encoding="utf-8")
JS = (ROOT / "web/admin.js").read_text(encoding="utf-8")
CSS = (ROOT / "web/admin.css").read_text(encoding="utf-8")
I18N = (ROOT / "web/i18n.js").read_text(encoding="utf-8")


def registry_keys(language):
    block = re.search(rf"{language}: \{{(.*?)\n  \}}", I18N, re.S).group(1)
    return set(re.findall(r"'([^']+)':", block))


def test_admin_html_uses_only_whitelisted_versioned_assets_and_no_inline_code():
    assert re.findall(r'<link[^>]+href="([^"]+)"', HTML) == [
        "/admin/static/style.css?v=3",
        "/admin/static/admin.css?v=11",
    ]
    assert re.findall(r'<script[^>]+src="([^"]+)"', HTML) == [
        "/admin/static/i18n.js?v=6",
        "/admin/static/admin.js?v=12",
    ]
    assert not re.search(r"<script(?![^>]+\bsrc=)[^>]*>", HTML, re.I)
    assert not re.search(r"\sstyle\s*=", HTML, re.I)
    assert not re.search(r"\son[a-z]+\s*=", HTML, re.I)
    assert '<meta name="robots" content="noindex,nofollow">' in HTML


def test_admin_i18n_keys_are_symmetric_and_used_keys_exist():
    en, zh = registry_keys("en"), registry_keys("zh")
    assert en == zh
    used = {f"admin.{key}" for key in re.findall(r"tr\('([^']+)'", JS)}
    used.update(re.findall(r'data-i18n="(admin\.[^"]+)"', HTML))
    assert used <= en, used - en
    assert {key for key in en if key.startswith("admin.")} <= zh
    assert "admin.heading" in en and "admin.bulkInterval" in en and "admin.showUnpriced" in en
    assert len(re.findall(r"<h1\b", HTML)) == 1
    assert HTML.count('data-i18n="admin.heading"') == 1
    assert '<h2 data-i18n="admin.heading"' not in HTML
    assert '<button id="logout"' in HTML and '<header>' in HTML
    assert 'data-i18n="nav.scores"' in HTML
    assert 'id="show-unpriced"' in HTML
    assert 'id="show-unpriced" type="checkbox"' in HTML
    assert ".bulk-bar[hidden], [hidden]" in CSS
    assert "white-space:nowrap" in CSS


def test_admin_price_formatter_and_shared_control_height():
    script = f"""
    const fs = require('fs'), vm = require('vm');
    const context = {{ window: {{}}, document: {{ querySelector: () => null, querySelectorAll: () => [] }}, fetch: () => {{}} }};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / 'web/admin.js'))}, 'utf8'), context);
    const h = context.window.adminHelpers;
    if (h.formatModelPrice({{price_in: 1.25, price_out: 10}}) !== '$1.25 / $10') process.exit(1);
    if (h.formatModelPrice({{price_in: null, price_out: 10}}) !== '—') process.exit(2);
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert "--control-h" in CSS
    assert ".admin-app button" in CSS
    assert 'id="key-status" class="admin-badge"' in HTML
    assert HTML.index('id="key-status"') < HTML.index('id="gateway-key"')


def test_admin_js_has_no_secret_storage_and_sets_admin_header_for_mutations():
    assert "localStorage" not in JS
    assert "sessionStorage" not in JS
    assert "X-Admin" in JS
    assert "init.headers = Object.assign({}, init.headers || {}, { 'X-Admin': '1' })" in JS
    assert re.search(r"if \(\(init\.method \|\| 'GET'\)\.toUpperCase\(\) !== 'GET'\)", JS)


def test_admin_js_passes_node_check():
    result = subprocess.run(["node", "--check", str(ROOT / "web/admin.js")], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr


def test_admin_helpers_cover_dirty_bulk_and_error_mapping():
    script = f"""
    const fs = require('fs'), vm = require('vm');
    const context = {{ window: {{}}, document: {{ querySelector: () => null, querySelectorAll: () => [] }}, fetch: () => {{}} }};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / 'web/admin.js'))}, 'utf8'), context);
    const h = context.window.adminHelpers;
    const original = {{ models: {{ default_dims: ['reasoning'], default_efforts: ['medium'], per_model: {{ a: {{ enabled: true }}, hidden: {{ enabled: false, interval_h: 9, dims: ['code'], efforts: ['low'] }} }} }} }};
    const collected = h.collectSettings(original);
    if (JSON.stringify(collected.models.per_model.hidden) !== JSON.stringify(original.models.per_model.hidden)) process.exit(3);
    const updated = h.bulkApply(original, ['a'], {{ interval_h: 3, dims: ['code'], efforts: ['high'] }});
    if (updated.models.per_model.a.interval_h !== 3 || updated.models.per_model.a.dims[0] !== 'code' || updated.models.per_model.a.enabled !== true) process.exit(1);
    if (JSON.stringify(updated.models.per_model.hidden) !== JSON.stringify(original.models.per_model.hidden)) process.exit(8);
    if (h.bulkValues('', ['code'], ['low']).error !== 'bulkInterval') process.exit(4);
    if (h.bulkValues('0', ['code'], ['low']).error !== 'bulkInterval') process.exit(4);
    if (h.bulkValues('2.5', ['code'], ['low']).error !== 'bulkInterval') process.exit(4);
    if (h.bulkValues('6', [], ['low']).error !== 'bulkDims') process.exit(5);
    if (h.bulkValues('6', ['code'], []).error !== 'bulkEfforts') process.exit(6);
    const ok = h.bulkValues('6', ['code'], ['low']);
    if (ok.error || ok.values.interval_h !== 6) process.exit(7);
    if (h.formatCount(840) !== '840' || h.formatCount(1000) !== '1K' || h.formatCount(12500) !== '12.5K' || h.formatCount(3200000) !== '3.2M' || h.formatCount(null) !== '—') process.exit(9);
    if (h.formatCount(h.weekly(120)) !== '840' || h.weekly(null) !== null) process.exit(10);
    const errors = h.errorFields([{{field: 'run.max_tokens', message: 'too high'}}]);
    if (errors['run.max_tokens'] !== 'too high') process.exit(2);
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

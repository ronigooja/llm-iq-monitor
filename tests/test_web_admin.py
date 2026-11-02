import json
import re
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]
HTML = (ROOT / "web/admin.html").read_text(encoding="utf-8")
JS = (ROOT / "web/admin.js").read_text(encoding="utf-8")
I18N = (ROOT / "web/i18n.js").read_text(encoding="utf-8")


def registry_keys(language):
    block = re.search(rf"{language}: \{{(.*?)\n  \}}", I18N, re.S).group(1)
    return set(re.findall(r"'([^']+)':", block))


def test_admin_html_uses_only_whitelisted_versioned_assets_and_no_inline_code():
    assert re.findall(r'<link[^>]+href="([^"]+)"', HTML) == [
        "/admin/static/style.css?v=1",
        "/admin/static/admin.css?v=1",
    ]
    assert re.findall(r'<script[^>]+src="([^"]+)"', HTML) == [
        "/admin/static/i18n.js?v=1",
        "/admin/static/admin.js?v=1",
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
    const context = {{ window: {{}}, document: {{}}, fetch: () => {{}} }};
    vm.createContext(context);
    vm.runInContext(fs.readFileSync({json.dumps(str(ROOT / 'web/admin.js'))}, 'utf8'), context);
    const h = context.window.adminHelpers;
    const original = {{ models: {{ per_model: {{ a: {{ enabled: true }} }} }} }};
    const updated = h.bulkApply(original, ['a'], {{ interval_h: 3, dims: ['code'], efforts: ['high'] }});
    if (updated.models.per_model.a.interval_h !== 3 || updated.models.per_model.a.dims[0] !== 'code') process.exit(1);
    const errors = h.errorFields([{{field: 'run.max_tokens', message: 'too high'}}]);
    if (errors['run.max_tokens'] !== 'too high') process.exit(2);
    """
    result = subprocess.run(["node", "-e", script], capture_output=True, text=True)
    assert result.returncode == 0, result.stderr

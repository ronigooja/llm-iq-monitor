import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_ui_grouping_and_history_helpers():
    rows = [
        {"sample_id": 1, "model": "zeta", "effort": "high", "prompt_key": "variant", "prompt": "Draw a penguin driving a tractor.", "svg": "<svg/>", "valid": 1, "created_at": 10},
        {"sample_id": 2, "model": "alpha", "effort": "low", "prompt_key": "classic", "prompt": "Draw a pelican riding a bicycle.", "svg": "<svg/>", "valid": 1, "created_at": 20},
        {"sample_id": 3, "model": "alpha", "effort": "low", "prompt_key": "classic", "prompt": "Draw a pelican riding a bicycle.", "svg": "<svg newer/>", "valid": 1, "created_at": 30},
        *({"sample_id": i, "model": "alpha", "effort": "low", "prompt_key": "classic", "prompt": "Draw a pelican riding a bicycle.", "svg": "<svg/>", "valid": 1, "created_at": i} for i in range(4, 12)),
        {"sample_id": 99, "model": "alpha", "effort": "low", "prompt_key": "classic", "prompt": "Draw a pelican riding a bicycle.", "svg": None, "valid": 0, "created_at": 1},
    ]
    harness = f"""
const fs = require('fs'), vm = require('vm');
const source = fs.readFileSync({json.dumps(str(ROOT / 'web/ui.js'))}, 'utf8');
const context = {{ window: {{}}, document: undefined }};
vm.runInNewContext(source, context);
const rows = {json.dumps(rows)};
const sections = context.window.groupSamples(rows);
const newest = sections[0].cards[0];
const history = context.window.historySamples(rows, newest);
if (sections.map(s => s.promptKey).join(',') !== 'classic,variant') throw Error('section order');
if (sections[0].cards[0].model !== 'alpha' || sections[0].cards[0].effort !== 'low' || sections[0].cards[0].sample_id !== 3) throw Error('newest/card order');
    if (history.length !== 4 || history.some(row => !row.svg) || history.some(row => row.sample_id === 99)) throw Error('history filtering');
console.log(JSON.stringify({{sections: sections.length, history: history.length}}));
"""
    result = subprocess.run(["node", "-e", harness], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"sections": 2, "history": 4}


def test_ui_card_key_round_trips_through_html_attribute_and_sorts_by_stars():
    rows = [
        {"sample_id": 1, "model": "zeta", "effort": "low", "prompt_key": "classic", "stars": None, "svg": "<svg/>", "valid": 1},
        {"sample_id": 2, "model": "alpha", "effort": "high", "prompt_key": "classic", "stars": 7, "svg": "<svg/>", "valid": 1},
        {"sample_id": 3, "model": "alpha", "effort": "low", "prompt_key": "classic", "stars": 7, "svg": "<svg/>", "valid": 1},
    ]
    harness = f"""
const fs = require('fs'), vm = require('vm');
const context = {{ window: {{}}, document: undefined }};
vm.runInNewContext(fs.readFileSync({json.dumps(str(ROOT / 'web/ui.js'))}, 'utf8'), context);
const key = context.window.cardKey({json.dumps(rows[2])});
if (/\\0|[\\x00-\\x1f\\x7f]/.test(key) || key !== 'alpha|low|classic') throw Error('unsafe card key');
const cards = context.window.groupSamples({json.dumps(rows)});
if (cards[0].cards.map(c => c.sample_id).join(',') !== '3,2,1') throw Error('star sort');
const html = `<button data-history="${{key}}"></button>`;
if (!html.includes('data-history="alpha|low|classic"')) throw Error('attribute round trip');
console.log(key);
"""
    result = subprocess.run(["node", "-e", harness], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == "alpha|low|classic"


def test_ui_design_has_untranslated_efforts_and_history_copy():
    script = (ROOT / "web/ui.js").read_text()
    assert "esc(sample.effort)" in script
    assert "'ui.history': 'History'" in script and "'ui.history': '历史'" in script
    assert "'ui.noHistory': 'No history yet'" in script and "'ui.noHistory': '暂无历史'" in script
    assert "<details" not in script
    assert "seed" not in script
    assert 'class="history-toggle"' in script
    assert 'aria-expanded="${shown}"' in script
    assert 'title="${tr(\'ui.history\')}"' in script
    assert '>◷</button>' in script
    assert '<div class="history-panel"><p class="muted">${tr(\'ui.noHistory\')}</p></div>' in script


def test_ui_sections_use_separate_kind_and_subject_i18n_elements():
    script = (ROOT / "web/ui.js").read_text()
    assert 'class="ui-section-heading"' in script
    assert 'class="ui-kind"' in script
    assert 'class="ui-subject"' in script
    assert "tr(`ui.${section.promptKey}`)" in script
    assert "tr(`ui.subject.${section.promptKey}`)" in script
    assert "const subject =" not in script


def test_ui_card_prefers_newest_valid_sample():
    rows = [
        {"sample_id": 1, "model": "m", "effort": "low", "prompt_key": "classic", "prompt": "p", "svg": "<svg old/>", "valid": 1, "created_at": 10},
        {"sample_id": 2, "model": "m", "effort": "low", "prompt_key": "classic", "prompt": "p", "svg": None, "valid": 0, "created_at": 20},
        {"sample_id": 3, "model": "n", "effort": "low", "prompt_key": "classic", "prompt": "p", "svg": None, "valid": 0, "created_at": 5},
        {"sample_id": 4, "model": "n", "effort": "low", "prompt_key": "classic", "prompt": "p", "svg": None, "valid": 0, "created_at": 7},
    ]
    harness = f"""
const fs = require('fs'), vm = require('vm');
const context = {{ window: {{}}, document: undefined }};
vm.runInNewContext(fs.readFileSync({json.dumps(str(ROOT / 'web/ui.js'))}, 'utf8'), context);
const cards = context.window.reduceSamples({json.dumps(rows)});
const byModel = Object.fromEntries(cards.map(c => [c.model, c.sample_id]));
console.log(JSON.stringify(byModel));
"""
    result = subprocess.run(["node", "-e", harness], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"m": 1, "n": 4}

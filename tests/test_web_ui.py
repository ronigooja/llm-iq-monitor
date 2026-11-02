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
if (history.length !== 6 || history.some(row => !row.svg) || history.some(row => row.sample_id === 99)) throw Error('history filtering');
console.log(JSON.stringify({{sections: sections.length, history: history.length}}));
"""
    result = subprocess.run(["node", "-e", harness], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"sections": 2, "history": 6}


def test_ui_design_has_untranslated_efforts_and_history_copy():
    script = (ROOT / "web/ui.js").read_text()
    assert "esc(sample.effort)" in script
    assert "'ui.history': 'History'" in script and "'ui.history': '历史'" in script
    assert "'ui.noHistory': 'No history yet'" in script and "'ui.noHistory': '暂无历史'" in script
    assert "<details" not in script
    assert "seed" not in script

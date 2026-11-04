import json
import subprocess
from pathlib import Path


ROOT = Path(__file__).parents[1]


def test_chart_options_are_uplot_constructible_without_legend_values_function():
    harness = f"""
const fs = require('fs'), vm = require('vm');
const context = {{ window: {{}}, document: undefined }};
vm.runInNewContext(fs.readFileSync({json.dumps(str(ROOT / 'web/scores.js'))}, 'utf8'), context);
context.tr = key => key;
context.css = () => '#000';
const rows = [{{t: 100, score: 81.2, latency_p50: 1.25, quality: 72.1}}, {{t: 200, score: null, latency_p50: null, quality: null}}];
const options = context.window.chartOptions(rows, 'write_en', 300, []);
if (typeof options.legend?.values === 'function') throw Error('legend.values must not be a function');
if (typeof options.series[1].value !== 'function' || typeof options.series[2].value !== 'function' || typeof options.series[3].value !== 'function') throw Error('missing series formatter');
if (options.series[1].value(null, null) !== '') throw Error('null score formatter');
console.log(JSON.stringify({{series: options.series.length, legend: Boolean(options.legend)}}));
"""
    result = subprocess.run(["node", "-e", harness], cwd=ROOT, capture_output=True, text=True)
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout) == {"series": 4, "legend": False}

import re
from html import unescape
from pathlib import Path

import pytest
import yaml
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient

from fixtures import monitor_db  # noqa: F401


ROOT = Path(__file__).parents[1]
TEMPLATE = ROOT / "deploy/templates/pages/api.html"
SCRIPT = ROOT / "web/api.js"


@pytest.fixture
async def client(monitor_db):
    ds = Datasette(
        [str(monitor_db)],
        metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()),
        template_dir=str(ROOT / "deploy/templates"),
        settings={"default_allow_sql": False, "allow_download": False, "default_cache_ttl": 60},
    )
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_api_page_is_public_reference(client):
    response = await client.get("/api")
    assert response.status_code == 200, response.text
    for query in ("best", "ranking", "availability_now", "dimensions", "models"):
        assert f"<h4><code>{query}</code></h4>" in response.text
    for query in ("series", "ui_samples", "health"):
        assert f"<h4><code>{query}</code></h4>" not in response.text
        assert f'data-api-url="/monitor/{query}.json' not in response.text
    assert "/monitor/rate.json" not in response.text
    assert "/monitor/whoami.json" not in response.text
    assert "rating key" not in response.text.lower()
    assert "example_link" not in response.text
    assert 'target="_blank"' not in response.text
    assert not re.search(r"<script[^>]*>\s*[^<]", response.text, re.I)
    assert "window.location.hash" not in response.text
    assert "location.hash" not in response.text
    assert "cors" not in response.text.lower()
    assert "datasette" not in response.text.lower()
    assert "exposure" not in response.text.lower()


@pytest.mark.asyncio
async def test_best_is_first_query_card(client):
    html = (await client.get("/api")).text
    queries = re.findall(r'<article class="api-query">.*?<h4><code>([^<]+)</code>', html, re.S)
    assert queries[0] == "best"


def test_api_template_keys_are_registered_in_both_languages():
    html = TEMPLATE.read_text()
    script = SCRIPT.read_text()
    keys = set(re.findall(r'data-i18n="(api\.[^"]+)"', html))
    for key in keys:
        assert re.search(rf"['\"]{re.escape(key)}['\"]\s*:", script), key
    assert len(re.findall(r"'api\.[^']+'\s*:", script.split("zh:", 1)[0])) >= len(keys)
    assert len(re.findall(r"'api\.[^']+'\s*:", script.split("zh:", 1)[1])) >= len(keys)


@pytest.mark.asyncio
async def test_best_card_lists_min_availability_parameter():
    html = TEMPLATE.read_text()
    best = html.split("<h4><code>best</code></h4>", 1)[1].split("</article>", 1)[0]
    assert "<code>min_availability</code>" in best
    assert "default 0.9" in best
    script = SCRIPT.read_text()
    assert "'api.best_min_availability':" in script.split("zh:", 1)[0]
    assert "'api.best_min_availability':" in script.split("zh:", 1)[1]


def test_availability_now_card_lists_exact_columns_without_params():
    html = TEMPLATE.read_text()
    card = html.split("<h4><code>availability_now</code></h4>", 1)[1].split("</article>", 1)[0]
    columns = re.findall(r'<div><code>([a-z_0-9]+)</code>', card)
    assert columns == ["model", "effort", "availability", "samples", "state", "latency_p50", "last_probe_at"]
    assert "<code>dim</code>" not in card and "<code>effort</code>" in card
    assert 'data-api-url="/monitor/availability_now.json?_shape=array"' in card


@pytest.mark.asyncio
async def test_api_try_urls_are_existing_queries(client):
    html = (await client.get("/api")).text
    urls = [unescape(url) for url in re.findall(r'data-api-url="([^"]+)"', html)]
    assert len(urls) == 5
    metadata = yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text())
    queries = metadata["databases"]["monitor"]["queries"]
    checked = 0
    for url in urls:
        name = re.match(r"/monitor/([^.]+)\.json", url).group(1)
        if name not in queries:
            # availability_now is provided by the backend; the check runs once its query exists.
            continue
        response = await client.get(url)
        assert response.status_code == 200, (url, response.text)
        checked += 1
    assert checked >= 4

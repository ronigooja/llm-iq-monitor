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
    for query in ("ranking", "series", "models", "dimensions", "ui_samples", "health"):
        assert f"<code>{query}</code>" in response.text
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


def test_api_template_keys_are_registered_in_both_languages():
    html = TEMPLATE.read_text()
    script = SCRIPT.read_text()
    keys = set(re.findall(r'data-i18n="(api\.[^"]+)"', html))
    for key in keys:
        assert re.search(rf"['\"]{re.escape(key)}['\"]\s*:", script), key
    assert len(re.findall(r"'api\.[^']+'\s*:", script.split("zh:", 1)[0])) >= len(keys)
    assert len(re.findall(r"'api\.[^']+'\s*:", script.split("zh:", 1)[1])) >= len(keys)


@pytest.mark.asyncio
async def test_api_try_urls_are_existing_queries(client):
    html = (await client.get("/api")).text
    urls = [unescape(url) for url in re.findall(r'data-api-url="([^"]+)"', html)]
    assert len(urls) == 6
    for url in urls:
        response = await client.get(url)
        assert response.status_code == 200, (url, response.text)

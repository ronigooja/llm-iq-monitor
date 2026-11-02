import re
from pathlib import Path

import pytest
import yaml
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient

from fixtures import monitor_db  # noqa: F401


ROOT = Path(__file__).parents[1]
TEMPLATES = [ROOT / "deploy/templates/index.html", ROOT / "deploy/templates/pages/compare.html", ROOT / "deploy/templates/pages/ui.html"]


def _registry_keys(language):
    source = (ROOT / "web/i18n.js").read_text()
    block = re.search(rf"{language}: \{{(.*?)\n  \}}", source, re.S).group(1)
    return set(re.findall(r"'([^']+)':", block))


def test_i18n_registry_is_symmetric_and_template_keys_exist():
    en, zh = _registry_keys("en"), _registry_keys("zh")
    assert en == zh
    used = set().union(*(set(re.findall(r'data-i18n="([^"]+)"', p.read_text())) for p in TEMPLATES))
    assert used <= en


@pytest.fixture
async def web_client(monitor_db):
    ds = Datasette(
        [str(monitor_db)],
        metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()),
        template_dir=str(ROOT / "deploy/templates"),
        static_mounts=[("static", str(ROOT / "web"))],
        settings={"default_allow_sql": False, "allow_download": False},
    )
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_web_pages_have_i18n_header_and_ui_csp(web_client):
    for path in "/", "/compare", "/ui":
        response = await web_client.get(path)
        assert response.status_code == 200, (path, response.text)
        body = response.text
        assert 'id="lang-switch"' in body
        assert 'href="/api"' in body
        assert '/static/i18n.js?v=9' in body
    ui = (await web_client.get("/ui")).text
    assert "Content-Security-Policy" in ui
    assert not re.search(r"<script[^>]*>\s*[^<]+", ui)


def test_dimensions_query_keeps_display_order_and_text():
    metadata = yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text())
    sql = metadata["databases"]["monitor"]["queries"]["dimensions"]["sql"]
    assert "'reasoning'" in sql and "'ui'" in sql
    assert sql.index("'reasoning'") < sql.index("'code'") < sql.index("'instruction'") < sql.index("'write_zh'") < sql.index("'write_en'") < sql.index("'ui'")

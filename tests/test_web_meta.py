import re
from html.parser import HTMLParser
from pathlib import Path

import pytest
import yaml
from datasette.app import Datasette
from httpx import ASGITransport, AsyncClient

from fixtures import monitor_db  # noqa: F401


ROOT = Path(__file__).parents[1]
PAGES = {
    "/": (
        "LLM IQ Monitor · 大模型分项能力评分",
        "Scheduled LLM benchmark by capability: reasoning, code, instruction following, writing, drawing. 按能力定时评测大模型：推理、代码、指令遵循、写作、绘图，含耗时与成本。",
    ),
    "/compare": (
        "模型对比 Compare · LLM IQ Monitor",
        "Side-by-side score, time to solve and cost per model and effort. 按模型和推理档位并排对比分数、解题时间和成本。",
    ),
    "/ui": (
        "SVG 绘图样本 · LLM IQ Monitor",
        "SVG drawings by each model, such as a pelican riding a bicycle. 各模型生成的 SVG 绘图样本，例如骑自行车的鹈鹕。",
    ),
    "/availability": (
        "可用性 Availability · LLM IQ Monitor",
        "Current probe availability and state of each model and effort, with history. 各模型和推理档位的当前探测可用率、状态与历史。",
    ),
    "/api": (
        "API 参考 · LLM IQ Monitor",
        "Public read-only JSON API for scores, history and dimensions. 公开只读 JSON 接口：评分、历史、能力维度。",
    ),
}


class HeadParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.title = []
        self.meta = []
        self.in_title = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "title":
            self.in_title = True
        elif tag == "meta":
            self.meta.append(attrs)

    def handle_endtag(self, tag):
        if tag == "title":
            self.in_title = False

    def handle_data(self, data):
        if self.in_title:
            self.title.append(data)


@pytest.fixture
async def client(monitor_db):
    ds = Datasette(
        [str(monitor_db)],
        metadata=yaml.safe_load((ROOT / "deploy/metadata.yaml").read_text()),
        template_dir=str(ROOT / "deploy/templates"),
        settings={"default_allow_sql": False, "allow_download": False},
    )
    async with AsyncClient(transport=ASGITransport(app=ds.app()), base_url="http://test") as c:
        yield c


@pytest.mark.asyncio
async def test_pages_have_bilingual_static_share_metadata(client):
    for path, (title, description) in PAGES.items():
        response = await client.get(path)
        assert response.status_code == 200, (path, response.text)
        parser = HeadParser()
        parser.feed(response.text)
        assert len(parser.title) == 1
        assert re.search(r"[\u3400-\u9fff]", title) and re.search(r"[A-Za-z]", title)
        assert re.search(r"[\u3400-\u9fff]", description) and re.search(r"[A-Za-z]", description)
        assert "".join(parser.title) == title
        metas = {(m.get("property") or m.get("name")): m.get("content") for m in parser.meta}
        assert metas["description"] == description
        assert metas["og:title"] == title
        assert metas["og:description"] == description
        assert metas["og:type"] == "website"
        assert metas["og:site_name"] == "LLM IQ Monitor"


def test_meta_keys_are_registered_for_both_languages_and_each_page():
    source = (ROOT / "web/i18n.js").read_text()
    assert "registry[language]['meta.title']" in source
    assert "registry[language]['meta.description']" in source
    for page in ("scores", "compare", "ui", "availability", "api"):
        assert f"{page}:" in source
    assert re.search(r"en: \{ title:'[^']*[A-Za-z]", source)
    assert re.search(r"zh: \{ title:'[^']*[\u3400-\u9fff]", source)


@pytest.mark.asyncio
async def test_all_page_assets_use_version_24(client):
    for path in PAGES:
        body = (await client.get(path)).text
        versions = set(re.findall(r"/static/[\w./-]+\?v=(\d+)", body))
        assert versions == {"30"}, (path, versions)
        assert "?v=17" not in body

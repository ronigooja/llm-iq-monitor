import httpx
import pytest
from llm_iq_monitor.db import connect
from llm_iq_monitor.discovery import list_models, sync_enabled, sync_models
from llm_iq_monitor.settings import Settings


@pytest.mark.asyncio
async def test_discovery():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})))
    assert await list_models("https://models", "secret", client) == ["a", "b"]
    await client.aclose()
    conn = connect(":memory:")
    sync_models(conn, ["a", "b"]); sync_models(conn, ["b"])
    assert conn.execute("select active from models where id='a'").fetchone()[0] == 0


def test_sync_enabled_defaults_unconfigured_models_to_disabled():
    conn = connect(":memory:")
    sync_models(conn, ["enabled", "disabled", "missing"])
    settings = Settings.model_validate({"models": {"enabled": {"enabled": True}}})
    sync_enabled(conn, settings)
    assert dict(conn.execute("SELECT id, enabled FROM models").fetchall()) == {
        "enabled": 1, "disabled": 0, "missing": 0,
    }

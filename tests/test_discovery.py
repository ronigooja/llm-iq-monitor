import httpx
import pytest
from llm_iq_monitor.db import connect
from llm_iq_monitor.discovery import list_models, sync_models


@pytest.mark.asyncio
async def test_discovery():
    client = httpx.AsyncClient(transport=httpx.MockTransport(lambda r: httpx.Response(200, json={"data": [{"id": "a"}, {"id": "b"}]})))
    assert await list_models("https://models", "secret", client) == ["a", "b"]
    await client.aclose()
    conn = connect(":memory:")
    sync_models(conn, ["a", "b"]); sync_models(conn, ["b"])
    assert conn.execute("select active from models where id='a'").fetchone()[0] == 0

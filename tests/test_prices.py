import httpx
import pytest
from llm_iq_monitor.db import connect
from llm_iq_monitor.prices import refresh_prices, lookup


@pytest.mark.asyncio
async def test_refresh_and_etag():
    conn = connect(":memory:")
    calls = []
    def handler(request):
        calls.append(request)
        if request.headers.get("if-none-match") == '"x"': return httpx.Response(304)
        return httpx.Response(200, headers={"ETag": '"x"'}, json={"anthropic": {"models": {"m": {"cost": {"input": 1, "output": 2}}}}, "openai": {"models": {"m": {"cost": {"input": 3, "output": 4}}}}})
    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    assert await refresh_prices(conn, "https://prices", client)
    assert lookup(conn, "m") == ("anthropic", 1, 2)
    assert not await refresh_prices(conn, "https://prices", client)
    assert len(calls) == 2
    await client.aclose()

import asyncio
import json

import httpx
import pytest

from llm_iq_monitor.gateway import Gateway, GatewayError


def stream(*items):
    return "\n".join(f"data: {json.dumps(item)}" for item in items) + "\ndata: [DONE]\n"


@pytest.mark.asyncio
async def test_streaming_completion_records_timings_usage_and_finish_reason():
    transport = httpx.MockTransport(lambda request: httpx.Response(200, text=stream(
        {"choices": [{"delta": {"reasoning_content": "think"}, "finish_reason": None}]},
        {"choices": [{"delta": {"content": "answer"}, "finish_reason": "stop"}]},
        {"choices": [], "usage": {"prompt_tokens": 4, "completion_tokens": 7,
                                    "completion_tokens_details": {"reasoning_tokens": 2}}},
    ), headers={"content-type": "text/event-stream"}))
    async with httpx.AsyncClient(transport=transport) as client:
        result = await Gateway("https://gateway.test/v1", client=client).chat(
            "model", [], effort="high", max_tokens=10)
    assert result.reply == "answer"
    assert result.latency_s >= result.ttft_s >= 0
    assert result.reasoning_ttft_s >= 0
    assert (result.in_tok, result.out_tok, result.reasoning_tok) == (4, 7, 2)
    assert result.finish_reason == "stop"


@pytest.mark.asyncio
async def test_gateway_errors_and_http_400_unsupported():
    async def call(status, text=""):
        transport = httpx.MockTransport(lambda request: httpx.Response(status, text=text))
        async with httpx.AsyncClient(transport=transport) as client:
            return await Gateway("https://gateway.test", client=client).chat(
                "m", [], effort="low", max_tokens=1)

    with pytest.raises(GatewayError, match="HTTP 500") as exc:
        await call(500)
    assert exc.value.error == "http_error" and not exc.value.unsupported
    with pytest.raises(GatewayError) as exc:
        await call(400, "level not supported")
    assert exc.value.error == "http_error" and exc.value.unsupported
    with pytest.raises(GatewayError) as exc:
        await call(400, "bad request")
    assert exc.value.error == "http_error" and not exc.value.unsupported

    empty = httpx.MockTransport(lambda request: httpx.Response(
        200, text="data: {\"choices\":[{\"delta\":{}}]}\ndata: [DONE]\n"))
    async with httpx.AsyncClient(transport=empty) as client:
        with pytest.raises(GatewayError, match="empty_reply"):
            await Gateway("https://gateway.test", client=client).chat("m", [], effort="low", max_tokens=1)


@pytest.mark.asyncio
async def test_gateway_timeout_and_rtt_fallback(monkeypatch):
    def timeout(request):
        raise httpx.ReadTimeout("slow")
    async with httpx.AsyncClient(transport=httpx.MockTransport(timeout)) as client:
        with pytest.raises(GatewayError) as exc:
            await Gateway("https://gateway.test", client=client).chat("m", [], effort="low", max_tokens=1)
    assert exc.value.error == "timeout"
    monkeypatch.setattr(asyncio, "open_connection", lambda *a: (_ for _ in ()).throw(OSError("offline")))
    assert await Gateway("https://no-route.test").connect_rtt_ms(42, attempts=2) == 42


@pytest.mark.asyncio
async def test_rtt_uses_median(monkeypatch):
    class Writer:
        def close(self): pass
    async def connect(*args):
        return None, Writer()
    # Patch the clock around the real implementation rather than sleeping.
    clock = iter([0, .003, .003, .004, .004, .006])
    monkeypatch.setattr(asyncio, "open_connection", connect)
    async def immediate(awaitable, timeout):
        return await awaitable
    monkeypatch.setattr("llm_iq_monitor.gateway.asyncio.wait_for", immediate)
    monkeypatch.setattr("llm_iq_monitor.gateway.time.perf_counter", lambda: next(clock))
    result = await Gateway("http://127.0.0.1").connect_rtt_ms(99, attempts=3)
    assert result == pytest.approx(2)


def test_secret_str_key_is_unwrapped_in_auth_header():
    import httpx
    from pydantic import SecretStr
    from llm_iq_monitor.gateway import Gateway

    gw = Gateway("http://x/v1", SecretStr("abc123"))
    assert gw.api_key == "abc123"

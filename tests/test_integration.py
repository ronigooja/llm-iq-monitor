import json
from pathlib import Path
from types import SimpleNamespace

import httpx
import pytest
import yaml
from datasette.app import Datasette

from llm_iq_monitor import db, sandbox
from llm_iq_monitor.gateway import Gateway
from llm_iq_monitor.questions.base import Question
from llm_iq_monitor.runner import run_model


@pytest.mark.asyncio
async def test_full_cycle_real_db_and_datasette(tmp_path, monkeypatch):
    conn = db.connect(tmp_path / "monitor.db")
    conn.execute("INSERT INTO models VALUES ('demo', 1, 0, 0, NULL, 1)")
    conn.execute("INSERT INTO prices VALUES ('demo', 'openai', 2, 4, 1234)")
    questions = {
        dim: Question(f"{dim}-1", dim, f"prompt-{dim}", "code" if dim == "code" else "exact",
                      "ok" if dim != "code" else None,
                      {"tests": []} if dim == "code" else {})
        for dim in ("trap", "math", "logic", "code", "instruction", "science")
    }
    monkeypatch.setattr("llm_iq_monitor.runner._generate", lambda dim, seed: [questions[dim]])
    async def fake_code_runner(code, tests):
        return True
    async def _ok(question, reply): return True
    monkeypatch.setattr(sandbox, "ascore_code", _ok)

    def handler(request):
        payload = json.loads(request.content)
        prompt = payload["messages"][0]["content"]
        content = "```python\ndef solve(*args):\n    return None\n```" if "prompt-code" in prompt else "ANSWER: ok"
        chunks = [
            {"choices": [{"delta": {"reasoning_content": "r"}}]},
            {"choices": [{"delta": {"content": content}, "finish_reason": "stop"}]},
            {"choices": [], "usage": {"prompt_tokens": 10, "completion_tokens": 20,
                                       "completion_tokens_details": {"reasoning_tokens": 2}}},
        ]
        body = "\n".join("data: " + json.dumps(chunk) for chunk in chunks) + "\ndata: [DONE]\n"
        return httpx.Response(200, text=body, headers={"content-type": "text/event-stream"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        gateway = Gateway("http://gateway.test/v1", client=client)
        monkeypatch.setattr(gateway, "connect_rtt_ms", lambda *args: 50)
        settings = SimpleNamespace(
            gateway=SimpleNamespace(base_url="http://gateway.test/v1", api_key=None),
            run=SimpleNamespace(max_tokens=100, timeout_s=10),
            net=SimpleNamespace(rtt_fallback_ms=30),
            effective=lambda model: SimpleNamespace(
                dims=list(questions), efforts=["high", "low"]),
        )
        ids = await run_model("demo", settings=settings, conn=conn, db=db,
                              gateway=gateway, tick_time=1790899200)
    assert len(ids) == 2
    runs = conn.execute("SELECT * FROM runs ORDER BY id").fetchall()
    results = conn.execute("SELECT * FROM results ORDER BY id").fetchall()
    dims = conn.execute("SELECT * FROM run_dims ORDER BY run_id, dim").fetchall()
    assert [r["effort"] for r in runs] == ["low", "high"]
    assert all(r["status"] == "ok" for r in runs)
    assert all(r["rtt_ms"] == 50 and r["price_in"] == 2 and r["price_out"] == 4 for r in runs)
    assert len(results) == 12 and len(dims) == 12
    assert all(r["correct"] == 1 and r["error"] is None for r in results)
    assert all(d["score"] == 100 and d["n"] == 1 and d["n_err"] == 0 for d in dims)
    assert all(d["latency_p50"] >= 0 and d["cost_usd"] == pytest.approx(0.0001) for d in dims)
    assert all("overall" not in r.keys() for r in runs)

    root = Path(__file__).parents[1]
    datasette = Datasette([str(tmp_path / "monitor.db")],
                          metadata=yaml.safe_load((root / "deploy/metadata.yaml").read_text()),
                          settings={"default_allow_sql": False})
    from httpx import ASGITransport, AsyncClient
    async with AsyncClient(transport=ASGITransport(app=datasette.app()), base_url="http://test") as client:
        for query, params in (("ranking", {"dim": "math", "effort": ""}),
                              ("series", {"model": "demo", "effort": "low", "dim": "math",
                                           "from": "", "to": "", "dataset_version": ""}),
                              ("models", {}), ("health", {})):
            response = await client.get(f"/monitor/{query}.json", params={**params, "_shape": "array"})
            assert response.status_code == 200, response.text
            assert response.json()

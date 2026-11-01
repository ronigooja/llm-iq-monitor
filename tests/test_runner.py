import json
from types import SimpleNamespace

import pytest

from llm_iq_monitor.gateway import Completion
from llm_iq_monitor.runner import run_model


class DB:
    def __init__(self): self.runs = []; self.results = []
    def lookup(self, conn, model): return ("openai", 1.0, 2.0, 123.0)
    def create_run(self, conn, **fields): self.runs.append(fields); return len(self.runs)
    def insert_result(self, conn, run_id, **fields): self.results.append((run_id, fields))
    def finish_run(self, conn, run_id, **fields): self.runs[run_id - 1].update(fields)


@pytest.mark.asyncio
async def test_runner_serializes_efforts_and_persists_raw_results(monkeypatch):
    q = SimpleNamespace(qid="q1", kind="exact", expected="yes", prompt="p")
    monkeypatch.setattr("llm_iq_monitor.runner._generate", lambda dim, seed: [q])
    async def score(q, reply):
        return True
    monkeypatch.setattr("llm_iq_monitor.runner._score", score)
    calls = []
    class Gateway:
        async def chat(self, *args, effort, **kwargs):
            calls.append(effort)
            return Completion("ANSWER: yes", 1, .2, .1, 2, 3, 1, "stop")
        async def connect_rtt_ms(self, *args): return 5
    settings = SimpleNamespace(
        gateway=SimpleNamespace(base_url="http://x", api_key=None),
        run=SimpleNamespace(max_tokens=20, timeout_s=4),
        net=SimpleNamespace(rtt_fallback_ms=30),
        effective=lambda model: SimpleNamespace(dims=["math"], efforts=["high", "low", "medium"]),
    )
    db = DB()
    monkeypatch.setattr("llm_iq_monitor.runner._lazy", lambda name: __import__(name, fromlist=["*"]) if name.endswith("aggregate") else db)
    # Supply a no-op aggregate module while retaining the real runner DB fake.
    import llm_iq_monitor.aggregate as aggregate
    monkeypatch.setattr(aggregate, "finalize_run", lambda conn, run_id: None)
    ids = await run_model("m", settings=settings, conn=object(), db=db, gateway=Gateway(), tick_time=0)
    assert ids == [1, 2, 3] and calls == ["low", "medium", "high"]
    assert all(run["rtt_ms"] == 5 for run in db.runs)
    assert all(result[1]["correct"] is True or result[1]["correct"] == 1 for result in db.results)
    assert json.loads(db.runs[0]["params"])["reasoning_effort"] == "low"

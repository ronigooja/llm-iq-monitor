"""Execute one model/effort cycle and persist raw observations."""
from __future__ import annotations
import inspect
import json
import time
from typing import Any


def _v(obj, key, default=None):
    return obj.get(key, default) if isinstance(obj, dict) else getattr(obj, key, default)


async def _call(fn, *args, **kwargs):
    value = fn(*args, **kwargs)
    return await value if inspect.isawaitable(value) else value


async def run_model(model: str, *, settings, conn=None, db=None, gateway=None,
                    tick_time: float | None = None, trigger: str = "schedule",
                    dimensions=None, efforts=None, seed: str | None = None):
    """Run selected efforts serially. Dependencies may be passed as fakes."""
    db = db or _lazy("llm_iq_monitor.db")
    if conn is None and hasattr(db, "connect"): conn = await _call(db.connect)
    effective = settings.effective(model)
    dimensions = list(dimensions or _v(effective, "dims", []))
    efforts = list(efforts or _v(effective, "efforts", ["medium"]))
    efforts = [x for x in ("low", "medium", "high") if x in efforts]
    seed = seed or time.strftime("%Y%m%d", time.gmtime(tick_time or time.time()))
    dataset_version = _question_version()
    params = {"max_tokens": _v(settings.run, "max_tokens"), "timeout_s": _v(settings.run, "timeout_s"),
              "reasoning_effort": None}
    gateway = gateway or _lazy("llm_iq_monitor.gateway").Gateway(
        _v(settings.gateway, "base_url"), _v(settings.gateway, "api_key"), timeout=_v(settings.run, "timeout_s"))
    price = await _price(db, conn, model)
    rtt = await _rtt(gateway, settings)
    out = []
    for effort in efforts:
        params["reasoning_effort"] = effort
        run_id = await _call(db.create_run, conn, model=model, effort=effort, seed=seed,
                             dataset_version=dataset_version, trigger=trigger,
                             dims=json.dumps(dimensions), params=json.dumps(params),
                             price_in=price[1] if price else None, price_out=price[2] if price else None,
                              price_fetched_at=price[3] if price and len(price) > 3 else None,
                              started_at=time.time(), status="running", rtt_ms=rtt)
        had_error = False
        unsupported = False
        try:
            for dim in dimensions:
                questions = _generate(dim, seed)
                if inspect.isawaitable(questions):
                    questions = await questions
                for question in questions:
                    started = time.perf_counter()
                    try:
                        reply = await gateway.chat(model, [{"role": "user", "content": question.prompt}],
                                                    effort=effort, max_tokens=_v(settings.run, "max_tokens"),
                                                    timeout=_v(settings.run, "timeout_s"))
                        if getattr(reply, "error", None): raise RuntimeError(reply.error)
                        correct = await _score(question, reply.reply)
                        fields = dict(qid=question.qid, dim=dim, correct=int(bool(correct)), error=None,
                                      finish_reason=reply.finish_reason, latency_s=reply.latency_s,
                                      ttft_s=reply.ttft_s, reasoning_ttft_s=reply.reasoning_ttft_s,
                                      in_tok=reply.in_tok, out_tok=reply.out_tok, reasoning_tok=reply.reasoning_tok,
                                      reply=reply.reply[:2000])
                    except Exception as exc:
                        if getattr(exc, "unsupported", False):
                            await _call(db.finish_run, conn, run_id, status="unsupported")
                            unsupported = True
                            break
                        had_error = True
                        fields = dict(qid=question.qid, dim=dim, correct=None,
                                      error=getattr(exc, "error", "network_error"), finish_reason=None,
                                      latency_s=time.perf_counter()-started, ttft_s=None,
                                      reasoning_ttft_s=None, in_tok=None, out_tok=None, reasoning_tok=None, reply=None)
                    if not unsupported:
                        await _call(db.insert_result, conn, run_id, **fields)
                else:
                    continue
                break
            if not unsupported:
                await _call(db.finish_run, conn, run_id, status="partial" if had_error else "ok",
                            finished_at=time.time())
                aggregate = _lazy("llm_iq_monitor.aggregate")
                await _call(aggregate.finalize_run, conn, run_id)
        except Exception:
            await _call(db.finish_run, conn, run_id, status="aborted")
            raise
        out.append(run_id)
    return out


async def _generate(dim, seed):
    from llm_iq_monitor.questions import generate
    value = generate(dim, seed)
    return await value if inspect.isawaitable(value) else value


async def _score(question, reply):
    if question.kind == "code":
        from llm_iq_monitor.sandbox import ascore_code
        return await ascore_code(question, reply)
    from llm_iq_monitor.scoring import score
    return await _call(score, question, reply)


async def _price(db, conn, model):
    if hasattr(db, "lookup"):
        value = db.lookup(conn, model)
        return await value if inspect.isawaitable(value) else value
    try:
        from llm_iq_monitor.prices import lookup
        return await _call(lookup, conn, model)
    except (ImportError, AttributeError): return None


def _lazy(name): return __import__(name, fromlist=["*"])
def _question_version():
    try:
        from llm_iq_monitor.questions.base import DATASET_VERSION
        return DATASET_VERSION
    except ImportError: return "v1"


async def _rtt(gateway, settings):
    measure = getattr(gateway, "connect_rtt_ms", None)
    if measure is None:
        return _v(settings.net, "rtt_fallback_ms", 30)
    return await _call(measure, _v(settings.net, "rtt_fallback_ms", 30), 3)

run = run_model

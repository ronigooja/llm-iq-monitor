"""Execute one model/effort cycle and persist raw observations."""
from __future__ import annotations
import inspect
import json
import time
import asyncio
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
              "max_attempts": _v(settings.run, "max_attempts", 3),
              "retry_delay_s": _v(settings.run, "retry_delay_s", 10),
              "reasoning_effort": None}
    gateway = gateway or _lazy("llm_iq_monitor.gateway").Gateway(
        _v(settings.gateway, "base_url"), _v(settings.gateway, "api_key"), timeout=_v(settings.run, "timeout_s"))
    price = await _price(db, conn, model)
    writing = any(dim in ("write_zh", "write_en") for dim in dimensions)
    judge_settings = getattr(settings, "judge", None)
    judge_model = getattr(judge_settings, "model", "claude-opus-5-5")
    judge_effort = getattr(judge_settings, "effort", "low")
    judge_price = await _price(db, conn, judge_model) if writing else None
    rtt = await _rtt(gateway, settings)
    out = []
    for effort in efforts:
        params["reasoning_effort"] = effort
        run_id = await _call(db.create_run, conn, model=model, effort=effort, seed=seed,
                             dataset_version=dataset_version, trigger=trigger,
                             dims=json.dumps(dimensions), params=json.dumps(params),
                              price_in=price[1] if price else None, price_out=price[2] if price else None,
                               price_fetched_at=price[3] if price and len(price) > 3 else None,
                               judge_model=judge_model if writing else None,
                               judge_price_in=judge_price[1] if judge_price else None,
                               judge_price_out=judge_price[2] if judge_price else None,
                               started_at=time.time(), status="running", rtt_ms=rtt)
        had_error = False
        unsupported = False
        aborted = False
        try:
            for dim in dimensions:
                questions = _generate(dim, seed)
                if inspect.isawaitable(questions):
                    questions = await questions
                for question in questions:
                    if dim == "ui":
                        prompt_key = _v(question, "meta", {}).get("prompt_key")
                        due = await _call(db.ui_sample_due, conn, model, effort, prompt_key,
                                           getattr(getattr(settings, "ui", None), "sample_max_age_days", 7)) if hasattr(db, "ui_sample_due") else True
                        if not due:
                            continue
                    started = time.perf_counter()
                    try:
                        reply = None
                        max_attempts = _v(settings.run, "max_attempts", 3)
                        retry_delay = _v(settings.run, "retry_delay_s", 10)
                        for attempt in range(max_attempts):
                            try:
                                reply = await gateway.chat(model, [{"role": "user", "content": question.prompt}],
                                                            effort=effort, max_tokens=_v(settings.run, "max_tokens"),
                                                            timeout=_v(settings.run, "timeout_s"))
                                if getattr(reply, "error", None):
                                    raise RuntimeError(reply.error)
                                break
                            except Exception as exc:
                                if getattr(exc, "unsupported", False):
                                    raise
                                if attempt + 1 >= max_attempts:
                                    raise
                                if retry_delay:
                                    await asyncio.sleep(retry_delay)
                        if dim == "ui":
                            ui_module = _lazy("llm_iq_monitor.ui")
                            svg, valid = ui_module.sanitize_svg(reply.reply)
                            fields = dict(qid=question.qid, dim=dim, correct=None, error=None,
                                          http_status=None, error_detail=None,
                                          finish_reason=reply.finish_reason, latency_s=reply.latency_s,
                                          ttft_s=reply.ttft_s, reasoning_ttft_s=reply.reasoning_ttft_s,
                                          in_tok=reply.in_tok, out_tok=reply.out_tok, reasoning_tok=reply.reasoning_tok,
                                          quality=None, judge_in_tok=None, judge_out_tok=None, judge_latency_s=None,
                                          reply=reply.reply[:2000])
                            await _call(db.insert_result, conn, run_id, **fields)
                            await _call(db.insert_ui_sample, conn, run_id, prompt_key,
                                         question.prompt, svg, valid)
                            continue
                        correct = False if reply.finish_reason == "length" else await _score(question, reply.reply)
                        fields = dict(qid=question.qid, dim=dim, correct=int(bool(correct)), error=None,
                                       http_status=None, error_detail=None,
                                      finish_reason=reply.finish_reason, latency_s=reply.latency_s,
                                      ttft_s=reply.ttft_s, reasoning_ttft_s=reply.reasoning_ttft_s,
                                      in_tok=reply.in_tok, out_tok=reply.out_tok, reasoning_tok=reply.reasoning_tok,
                                       quality=None, judge_in_tok=None, judge_out_tok=None, judge_latency_s=None,
                                       reply=reply.reply[:2000])
                        if question.kind == "rules" and dim in ("write_zh", "write_en"):
                            from llm_iq_monitor.judge import judge_reply
                            try:
                                judged = await judge_reply(
                                    gateway, judge_model, judge_effort, _v(question, "meta", {}).get("brief", {}),
                                    reply.reply, "zh" if dim == "write_zh" else "en",
                                    max_tokens=_v(settings.run, "max_tokens"), timeout=_v(settings.run, "timeout_s"),
                                )
                                fields.update(quality=judged.quality, judge_in_tok=judged.in_tok,
                                              judge_out_tok=judged.out_tok, judge_latency_s=judged.latency_s)
                            except Exception:
                                pass
                    except Exception as exc:
                        if getattr(exc, "unsupported", False):
                            await _call(db.finish_run, conn, run_id, status="unsupported")
                            unsupported = True
                            break
                        had_error = True
                        error_name = getattr(exc, "error", "network_error")
                        status = getattr(exc, "status", None)
                        detail = getattr(exc, "detail", None)
                        fields = dict(qid=question.qid, dim=dim, correct=None,
                                      error=error_name, http_status=status, error_detail=detail, finish_reason=None,
                                      latency_s=time.perf_counter()-started, ttft_s=None,
                                      reasoning_ttft_s=None, in_tok=None, out_tok=None, reasoning_tok=None,
                            quality=None, judge_in_tok=None, judge_out_tok=None, judge_latency_s=None, reply=None)
                        aborted = True
                        if dim == "ui" and hasattr(db, "insert_ui_sample"):
                            await _call(db.insert_ui_sample, conn, run_id, prompt_key,
                                         question.prompt, None, False)
                    if not unsupported:
                        await _call(db.insert_result, conn, run_id, **fields)
                    if aborted:
                        break
                else:
                    continue
                break
            if not unsupported and aborted:
                await _call(db.finish_run, conn, run_id, status="aborted", finished_at=time.time())
            elif not unsupported:
                await _call(db.finish_run, conn, run_id, status="partial" if had_error else "ok",
                            finished_at=time.time())
                aggregate = _lazy("llm_iq_monitor.aggregate")
                await _call(aggregate.finalize_run, conn, run_id)
        except Exception:
            await _call(db.finish_run, conn, run_id, status="aborted")
            raise
        out.append(run_id)
        if aborted:
            break
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

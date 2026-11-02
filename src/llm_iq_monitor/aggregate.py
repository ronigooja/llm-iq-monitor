"""Run aggregation."""
from __future__ import annotations
import math


def percentile(values, p):
    vals = sorted(v for v in values if v is not None)
    if not vals:
        return None
    if len(vals) == 1:
        return vals[0]
    pos = (len(vals) - 1) * p
    lo, hi = math.floor(pos), math.ceil(pos)
    return vals[lo] + (vals[hi] - vals[lo]) * (pos - lo)


def adjust(raw, rtt):
    if raw is None:
        return None
    return max(0.0, raw - (rtt or 0) / 1000)


def finalize_run(conn, run_id):
    run = conn.execute("SELECT * FROM runs WHERE id=?", (run_id,)).fetchone()
    if not run:
        raise ValueError(f"unknown run {run_id}")
    rows = conn.execute("SELECT * FROM results WHERE run_id=? ORDER BY id", (run_id,)).fetchall()
    rtt = run["rtt_ms"]
    dims = {}
    for row in rows:
        dims.setdefault(row["dim"], []).append(row)
    total_cost = 0.0
    has_cost = False
    total = len(rows)
    answered = sum(r["error"] is None for r in rows)
    for dim, items in dims.items():
        n = len(items); errors = sum(r["error"] is not None for r in items)
        good = [r for r in items if r["error"] is None]
        correct = sum(r["correct"] == 1 for r in good)
        if dim == "ui":
            score = None
        else:
            score = 100 * correct / n if n else None
        lat = [adjust(r["latency_s"], rtt) for r in good]
        ttft = [adjust(r["ttft_s"], rtt) for r in good]
        in_tok = sum(r["in_tok"] or 0 for r in items if r["in_tok"] is not None) or None
        out_tok = sum(r["out_tok"] or 0 for r in items if r["out_tok"] is not None) or None
        cost = None
        if (in_tok is not None or out_tok is not None) and run["price_in"] is not None and run["price_out"] is not None:
            cost = ((in_tok or 0) * run["price_in"] + (out_tok or 0) * run["price_out"]) / 1_000_000
        correct_cost = cost / correct if cost is not None and correct else None
        judged = [r["quality"] for r in items if r["quality"] is not None]
        quality = None if dim == "ui" else (sum(judged) / len(judged) if len(judged) >= n / 2 else None)
        judge_cost = None
        judge_in = sum(r["judge_in_tok"] or 0 for r in items if r["judge_in_tok"] is not None) or None
        judge_out = sum(r["judge_out_tok"] or 0 for r in items if r["judge_out_tok"] is not None) or None
        if (judge_in is not None or judge_out is not None) and run["judge_price_in"] is not None and run["judge_price_out"] is not None:
            judge_cost = ((judge_in or 0) * run["judge_price_in"] + (judge_out or 0) * run["judge_price_out"]) / 1_000_000
        if cost is not None: total_cost += cost; has_cost = True
        conn.execute("INSERT OR REPLACE INTO run_dims (run_id,dim,score,n,n_err,availability,latency_p50,latency_p95,ttft_p50,time_total,in_tok,out_tok,cost_usd,cost_per_correct,quality,judge_cost_usd) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                     (run_id, dim, score, n, errors, (n-errors)/n if n else None, percentile(lat,.5), percentile(lat,.95), percentile(ttft,.5), sum(r["latency_s"] or 0 for r in items), in_tok, out_tok, cost, correct_cost, quality, judge_cost))
    status = "ok" if not any(r["error"] is not None for r in rows) else "partial"
    duration = (run["finished_at"] - run["started_at"]) if run["finished_at"] is not None and run["started_at"] is not None else None
    if run["status"] not in {"aborted", "unsupported"}:
        conn.execute("UPDATE runs SET availability=?, duration_s=?, cost_usd=?, status=? WHERE id=?",
                     (answered / total if total else None, duration, total_cost if has_cost else None, status, run_id))
    else:
        conn.execute("UPDATE runs SET availability=?, duration_s=?, cost_usd=? WHERE id=?",
                     (answered / total if total else None, duration, total_cost if has_cost else None, run_id))

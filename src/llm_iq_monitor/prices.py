"""models.dev price cache."""
from __future__ import annotations
import logging, time
import httpx

log = logging.getLogger(__name__)


async def refresh_prices(conn, url, client=None):
    own = client is None
    if own: client = httpx.AsyncClient()
    try:
        headers = {}
        etag = conn.execute("SELECT value FROM meta WHERE key='prices.etag'").fetchone()
        if etag: headers["If-None-Match"] = etag[0]
        try:
            response = await client.get(url, headers=headers)
            if response.status_code == 304:
                return False
            response.raise_for_status()
            payload = response.json(); now = time.time()
            rows = []
            seen = set()
            providers = payload.get("providers", payload) if isinstance(payload, dict) else {}
            for provider in ("anthropic", "openai"):
                data = providers.get(provider, {}) if isinstance(providers, dict) else {}
                models = data.get("models", data) if isinstance(data, dict) else data
                iterable = models.items() if isinstance(models, dict) else ((m.get("id"), m) for m in models)
                for model, item in iterable:
                    if not model or model in seen or not isinstance(item, dict): continue
                    cost = item.get("cost", {})
                    if isinstance(cost, list): cost = cost[0] if cost else {}
                    if isinstance(cost, dict) and "input" in cost and "output" in cost:
                        rows.append((model, provider, cost["input"], cost["output"], now)); seen.add(model)
            conn.execute("BEGIN")
            conn.execute("DELETE FROM prices")
            conn.executemany("INSERT INTO prices(model,provider,input_usd_per_m,output_usd_per_m,fetched_at) VALUES (?,?,?,?,?)", rows)
            if response.headers.get("etag"):
                conn.execute("INSERT OR REPLACE INTO meta(key,value) VALUES('prices.etag',?)", (response.headers["etag"],))
            conn.execute("COMMIT")
            return True
        except Exception:
            if conn.in_transaction: conn.execute("ROLLBACK")
            log.exception("price refresh failed; keeping cached prices")
            return False
    finally:
        if own: await client.aclose()


def load_price_index(conn=None):
    if conn is None:
        from .db import connect
        conn = connect()
    return {r["model"]: (r["provider"], r["input_usd_per_m"], r["output_usd_per_m"]) for r in conn.execute("SELECT * FROM prices")}


def lookup(conn, model_id):
    row = conn.execute("SELECT provider,input_usd_per_m,output_usd_per_m FROM prices WHERE model=? ORDER BY CASE provider WHEN 'anthropic' THEN 0 WHEN 'openai' THEN 1 ELSE 2 END LIMIT 1", (model_id,)).fetchone()
    return tuple(row) if row else None

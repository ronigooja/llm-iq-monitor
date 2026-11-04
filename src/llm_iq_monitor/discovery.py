from __future__ import annotations
import time
import httpx


async def list_models(base_models_url, api_key, client=None):
    if hasattr(api_key, "get_secret_value"):
        api_key = api_key.get_secret_value()
    own = client is None
    if own: client = httpx.AsyncClient()
    try:
        response = await client.get(base_models_url, headers={"Authorization": f"Bearer {api_key}"})
        response.raise_for_status()
        data = response.json()
        return [x["id"] for x in data.get("data", []) if isinstance(x, dict) and x.get("id")]
    finally:
        if own: await client.aclose()


def sync_models(conn, ids):
    now = time.time(); ids = set(ids)
    conn.execute("UPDATE models SET active=0")
    for model in ids:
        conn.execute("INSERT INTO models(id,active,first_seen,last_seen) VALUES(?,?,?,?) ON CONFLICT(id) DO UPDATE SET active=1,last_seen=excluded.last_seen", (model, 1, now, now))


def sync_enabled(conn, settings):
    """Persist effective settings visibility for every known model."""
    conn.execute("UPDATE models SET enabled=0")
    for row in conn.execute("SELECT id FROM models"):
        if settings.effective(row[0]).enabled:
            conn.execute("UPDATE models SET enabled=1 WHERE id=?", (row[0],))

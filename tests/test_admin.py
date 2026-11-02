import json
import logging
import os
from pathlib import Path

import pytest
from starlette.testclient import TestClient

import llm_iq_monitor.admin as admin_module
from llm_iq_monitor.admin import create_app
from llm_iq_monitor.db import connect
from llm_iq_monitor.settings import ModelSettings, Settings, save_api_key, save_settings


TOKEN = "admin-token-for-tests-123456789"
KEY = "test-key-123"


@pytest.fixture
def admin_client(tmp_path, monkeypatch):
    config_dir = tmp_path / "config"
    data_dir = tmp_path / "data"
    monkeypatch.setenv("LLM_IQ_CONFIG_DIR", str(config_dir))
    monkeypatch.setenv("LLM_IQ_DATA_DIR", str(data_dir))

    conn = connect()
    conn.executemany(
        "INSERT INTO models(id, active, first_seen, last_seen, last_trigger_at) VALUES (?, 1, 1, 1, 1)",
        [("alpha",), ("beta",), ("unpriced",)],
    )
    conn.execute(
        "INSERT INTO prices(model, provider, input_usd_per_m, output_usd_per_m, fetched_at) VALUES (?, ?, ?, ?, ?)",
        ("alpha", "test", 1, 2, 1),
    )
    conn.close()

    save_settings(
        Settings(
            gateway={"base_url": "https://gateway.example/v1"},
            judge={"model": "alpha"},
            models={"per_model": {"alpha": ModelSettings(enabled=False)}},
        )
    )
    save_api_key(KEY)
    now = [1_000.0]
    app = create_app(token=TOKEN, clock=lambda: now[0])
    with TestClient(app, base_url="https://testserver") as client:
        yield client, now, config_dir, data_dir


def _login(client, token=TOKEN, ip="192.0.2.1, 192.0.2.2"):
    return client.post(
        "/admin/api/login",
        json={"token": token},
        headers={"X-Forwarded-For": ip},
    )


def _admin_headers():
    return {"X-Admin": "1"}


def test_login_lockout_uses_first_forwarded_ip_and_expiry(admin_client):
    client, now, *_ = admin_client
    for _ in range(4):
        assert _login(client, "wrong-token", "192.0.2.10, 198.51.100.10").status_code == 401
    assert _login(client, "wrong-token", "192.0.2.10, 203.0.113.10").status_code == 401
    assert _login(client, TOKEN, "192.0.2.10, 203.0.113.10").status_code == 429

    assert _login(client, TOKEN, "192.0.2.11").status_code == 204
    now[0] += 15 * 60
    assert _login(client, TOKEN, "192.0.2.10").status_code == 204

    for _ in range(4):
        assert _login(client, "wrong-token", "192.0.2.11").status_code == 401
    assert _login(client, TOKEN, "192.0.2.11").status_code == 204

    for _ in range(5):
        response = _login(client, "wrong-token", "192.0.2.12")
    assert response.status_code == 401
    assert _login(client, TOKEN, "192.0.2.12").status_code == 429


def test_login_cookie_flags_and_session_expiry(admin_client):
    client, now, *_ = admin_client
    response = _login(client)
    assert response.status_code == 204
    cookie = response.headers["set-cookie"]
    assert "HttpOnly" in cookie
    assert "Secure" in cookie
    assert "samesite=strict" in cookie.lower()
    assert "Path=/admin" in cookie
    assert "Max-Age=43200" in cookie

    assert client.get("/admin/api/state").status_code == 200
    now[0] += 12 * 60 * 60
    assert client.get("/admin/api/state").status_code == 401


def test_logout_invalidates_session_and_csrf_protects_writes(admin_client):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    assert client.get("/admin/api/state").status_code == 200
    assert client.post("/admin/api/logout").status_code == 403
    assert client.post("/admin/api/logout", headers=_admin_headers()).status_code == 204
    assert client.get("/admin/api/state").status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("get", "/admin/api/state"),
        ("post", "/admin/api/logout"),
        ("put", "/admin/api/settings"),
        ("put", "/admin/api/key"),
        ("post", "/admin/api/test"),
        ("post", "/admin/api/models/refresh"),
    ],
)
def test_protected_api_requires_session(admin_client, method, path):
    client, *_ = admin_client
    response = getattr(client, method)(path, json={}) if method != "get" else client.get(path)
    assert response.status_code == 401


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("post", "/admin/api/logout"),
        ("put", "/admin/api/settings"),
        ("put", "/admin/api/key"),
        ("post", "/admin/api/test"),
        ("post", "/admin/api/models/refresh"),
    ],
)
def test_authenticated_writes_require_x_admin(admin_client, method, path):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    response = getattr(client, method)(path, json={})
    assert response.status_code == 403


def test_state_never_returns_gateway_key(admin_client, caplog):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    caplog.set_level(logging.DEBUG)
    response = client.get("/admin/api/state")
    assert response.status_code == 200
    assert KEY not in response.content.decode()
    assert all(KEY not in value for value in response.headers.values())
    assert KEY not in caplog.text
    assert response.json()["key_set"] is True
    assert "api_key" not in json.dumps(response.json())


def test_state_models_expose_prices_and_priced_flag(admin_client):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    models = {item["id"]: item for item in client.get("/admin/api/state").json()["models"]}
    assert models["alpha"]["priced"] is True
    assert models["alpha"]["price_in"] == 1
    assert models["alpha"]["price_out"] == 2
    assert models["unpriced"]["priced"] is False
    assert models["unpriced"]["price_in"] is None
    assert models["unpriced"]["price_out"] is None


def test_settings_round_trip_and_validation_shape(admin_client):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    response = client.put(
        "/admin/api/settings",
        headers=_admin_headers(),
        json={"gateway": {"base_url": "https://changed.example/api"}, "judge": {"model": "alpha"}},
    )
    assert response.status_code == 200
    assert response.json()["settings"]["gateway"]["base_url"] == "https://changed.example/api"

    response = client.put(
        "/admin/api/settings",
        headers=_admin_headers(),
        json={"run": {"timeout_s": 0}},
    )
    assert response.status_code == 422
    assert set(response.json()) == {"errors"}
    assert all(set(error) == {"field", "message"} for error in response.json()["errors"])
    assert "traceback" not in response.text.lower()
    assert "pydantic" not in response.text.lower()


def test_unpriced_model_cannot_be_enabled(admin_client):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    response = client.put(
        "/admin/api/settings",
        headers=_admin_headers(),
        json={
            "gateway": {"base_url": "https://gateway.example/v1"},
            "judge": {"model": "alpha"},
            "models": {"per_model": {"unpriced": {"enabled": True}}},
        },
    )
    assert response.status_code == 422
    assert response.json() == {
        "errors": [{"field": "models.unpriced.enabled", "message": "model has no price"}]
    }


def test_key_update_is_minimal_and_mode_600(admin_client):
    client, _, config_dir, _ = admin_client
    assert _login(client).status_code == 204
    response = client.put("/admin/api/key", headers=_admin_headers(), json={"key": "replacement-key-456"})
    assert response.status_code == 200
    assert response.json() == {"key_set": True}
    secret_path = config_dir / "secrets.env"
    assert secret_path.stat().st_mode & 0o777 == 0o600
    assert secret_path.read_text() == "GATEWAY_API_KEY=replacement-key-456\n"


@pytest.mark.parametrize("path", ["/admin/api/test", "/admin/api/models/refresh"])
def test_gateway_errors_do_not_leak_key(admin_client, monkeypatch, caplog, path):
    client, *_ = admin_client
    assert _login(client).status_code == 204

    async def fail(settings):
        raise RuntimeError(f"gateway failed with {KEY}")

    if path.endswith("/test"):
        monkeypatch.setattr(admin_module, "test_connection", fail)
    else:
        monkeypatch.setattr(admin_module, "fetch_models", fail)
    caplog.set_level(logging.DEBUG)
    caplog.clear()
    response = client.post(path, headers=_admin_headers())
    assert response.status_code in {200, 502}
    assert KEY not in response.content.decode()
    assert all(KEY not in value for value in response.headers.values())
    assert KEY not in caplog.text


def test_static_whitelist_and_html_security_headers(admin_client, monkeypatch, tmp_path):
    web_dir = tmp_path / "web"
    web_dir.mkdir()
    (web_dir / "admin.html").write_text("<html>admin</html>")
    for name in ("admin.js", "admin.css", "i18n.js", "style.css"):
        (web_dir / name).write_text(name)
    monkeypatch.setattr(admin_module, "WEB_DIR", web_dir)
    client, *_ = admin_client

    html = client.get("/admin/")
    assert html.status_code == 200
    assert "Content-Security-Policy" in html.headers
    assert "default-src 'self'" in html.headers["Content-Security-Policy"]
    assert html.headers["Cache-Control"] == "no-store"
    assert html.headers["X-Content-Type-Options"] == "nosniff"
    assert html.headers["Referrer-Policy"] == "no-referrer"
    for name in ("admin.js", "admin.css", "i18n.js", "style.css"):
        assert client.get(f"/admin/static/{name}").status_code == 200
    for name in ("app.js", "admin.html", "../admin.js", "%2e%2e%2fadmin.js"):
        assert client.get(f"/admin/static/{name}").status_code == 404


def test_request_body_limit(admin_client):
    client, *_ = admin_client
    assert _login(client).status_code == 204
    response = client.put(
        "/admin/api/key",
        headers=_admin_headers(),
        content=json.dumps({"key": "x" * (64 * 1024)}),
    )
    assert response.status_code == 413


def test_create_app_requires_long_admin_token(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    with pytest.raises(RuntimeError):
        create_app()
    monkeypatch.setenv("ADMIN_TOKEN", "too-short")
    with pytest.raises(RuntimeError):
        create_app()
    assert create_app(token=TOKEN)


def test_main_does_not_start_without_valid_token(monkeypatch):
    monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    monkeypatch.setattr(admin_module.uvicorn, "run", lambda *args, **kwargs: None)
    with pytest.raises(RuntimeError):
        admin_module.main()

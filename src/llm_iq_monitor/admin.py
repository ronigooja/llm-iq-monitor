"""Authenticated ASGI administration service."""

from __future__ import annotations

import asyncio
import hmac
import json
import logging
import os
import secrets
import time
from dataclasses import dataclass, field
from datetime import timezone
from pathlib import Path
from typing import Any, Callable

import uvicorn
from pydantic import ValidationError
from starlette.applications import Starlette
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import HTMLResponse, JSONResponse, Response
from starlette.routing import Route

from .admin_logic import estimate_budget, fetch_models, model_rows, next_heartbeat_ticks, test_connection
from .db import connect
from .discovery import sync_models
from .prices import load_price_index
from .settings import DIMS, EFFORTS, Settings, load_settings, save_api_key, save_settings

log = logging.getLogger(__name__)

ADMIN_PREFIX = "/admin"
COOKIE_NAME = "llm_iq_monitor_admin"
SESSION_LIFETIME = 12 * 60 * 60
LOCKOUT_SECONDS = 15 * 60
MAX_BODY = 64 * 1024
STATIC_NAMES = {"admin.js", "admin.css", "i18n.js", "style.css"}
WEB_DIR = Path(__file__).resolve().parents[2] / "web"


@dataclass
class _Lock:
    failures: int = 0
    locked_until: float = 0


@dataclass
class AdminState:
    token: str
    clock: Callable[[], float] = time.time
    sessions: dict[str, float] = field(default_factory=dict)
    locks: dict[str, _Lock] = field(default_factory=dict)


def _headers(response: Response) -> Response:
    response.headers.setdefault("Cache-Control", "no-store")
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        response = await call_next(request)
        return _headers(response)


def _json(data: Any, status_code: int = 200, **kwargs: Any) -> JSONResponse:
    return _headers(JSONResponse(data, status_code=status_code, **kwargs))


def _client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for", "").split(",", 1)[0].strip()
    return forwarded or (request.client.host if request.client else "unknown")


def _csrf(request: Request) -> Response | None:
    if request.method in {"POST", "PUT"} and request.headers.get("x-admin") != "1":
        return _json({"error": "csrf header required"}, 403)
    return None


def _authenticated(request: Request, state: AdminState) -> bool:
    session = request.cookies.get(COOKIE_NAME)
    if not session:
        return False
    expiry = state.sessions.get(session)
    if expiry is None:
        return False
    if expiry <= state.clock():
        state.sessions.pop(session, None)
        return False
    return True


async def _body_json(request: Request) -> tuple[dict[str, Any] | None, Response | None]:
    length = request.headers.get("content-length")
    if length:
        try:
            if int(length) > MAX_BODY:
                return None, _json({"error": "request body too large"}, 413)
        except ValueError:
            return None, _json({"error": "invalid content length"}, 400)
    body = await request.body()
    if len(body) > MAX_BODY:
        return None, _json({"error": "request body too large"}, 413)
    try:
        value = json.loads(body or b"{}")
    except (ValueError, UnicodeDecodeError):
        return None, _json({"error": "invalid JSON"}, 400)
    if not isinstance(value, dict):
        return None, _json({"error": "JSON object required"}, 422)
    return value, None


def _auth_error(request: Request, state: AdminState) -> Response | None:
    if not _authenticated(request, state):
        return _json({"error": "authentication required"}, 401)
    csrf = _csrf(request)
    if csrf is not None:
        return csrf
    return None


def _settings_dump(settings: Settings) -> dict[str, Any]:
    return settings.model_dump(mode="json", exclude={"gateway": {"api_key"}}, exclude_none=True)


def _state_payload() -> dict[str, Any]:
    settings = load_settings()
    conn = connect()
    try:
        model_ids = [row["id"] for row in conn.execute("SELECT id FROM models ORDER BY id")]
        price_index = load_price_index(conn)
    finally:
        conn.close()
    rows = model_rows(settings, model_ids, price_index)
    ticks = next_heartbeat_ticks(settings.schedule.heartbeat_cron)
    budget = estimate_budget(settings)
    return {
        "settings": _settings_dump(settings),
        "key_set": settings.gateway.api_key is not None,
        "models": rows,
        "dims": list(DIMS),
        "efforts": list(EFFORTS),
        "heartbeat_next": [tick.astimezone(timezone.utc).isoformat().replace("+00:00", "Z") for tick in ticks],
        "budget": {
            "runs_per_day": budget["runs_per_day"],
            "tokens_per_day": budget["input_tokens_per_day"] + budget["output_tokens_with_thinking_per_day"],
        },
    }


def _validation_errors(exc: ValidationError) -> list[dict[str, str]]:
    result = []
    for item in exc.errors():
        loc = ".".join(str(part) for part in item.get("loc", ())) or "settings"
        message = str(item.get("msg", "invalid value"))
        if message.startswith("Value error, "):
            message = message[13:]
        result.append({"field": loc, "message": message})
    return result


async def index(request: Request) -> Response:
    try:
        content = (WEB_DIR / "admin.html").read_text(encoding="utf-8")
    except OSError:
        return _json({"error": "admin page unavailable"}, 404)
    response = HTMLResponse(content)
    response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'"
    return _headers(response)


async def static_file(request: Request) -> Response:
    name = request.path_params.get("name", "")
    if name not in STATIC_NAMES:
        return _json({"error": "not found"}, 404)
    path = WEB_DIR / name
    try:
        content = path.read_bytes()
    except OSError:
        return _json({"error": "not found"}, 404)
    media = "application/javascript" if name.endswith(".js") else "text/css"
    return _headers(Response(content, media_type=media))


async def login(request: Request) -> Response:
    state: AdminState = request.app.state.admin
    data, error = await _body_json(request)
    if error is not None:
        return error
    supplied = data.get("token") if data else None
    supplied = supplied if isinstance(supplied, str) else ""
    now = state.clock()
    ip = _client_ip(request)
    lock = state.locks.setdefault(ip, _Lock())
    if lock.locked_until > now:
        response = _json({"error": "temporarily locked"}, 429)
        response.headers["Retry-After"] = str(max(1, int(lock.locked_until - now)))
        return response
    if lock.locked_until and lock.locked_until <= now:
        lock.failures = 0
        lock.locked_until = 0
    if not hmac.compare_digest(supplied, state.token):
        await asyncio.sleep(0.01)
        lock.failures += 1
        if lock.failures >= 5:
            lock.locked_until = now + LOCKOUT_SECONDS
        return _json({"error": "invalid token"}, 401)
    state.locks.pop(ip, None)
    session = secrets.token_urlsafe(32)
    state.sessions[session] = now + SESSION_LIFETIME
    response = _headers(Response(status_code=204))
    response.set_cookie(COOKIE_NAME, session, max_age=SESSION_LIFETIME, httponly=True, secure=True, samesite="strict", path=ADMIN_PREFIX)
    return response


async def logout(request: Request) -> Response:
    state: AdminState = request.app.state.admin
    error = _auth_error(request, state)
    if error is not None:
        return error
    session = request.cookies.get(COOKIE_NAME)
    if session:
        state.sessions.pop(session, None)
    response = _headers(Response(status_code=204))
    response.delete_cookie(COOKIE_NAME, path=ADMIN_PREFIX)
    return response


async def state(request: Request) -> Response:
    error = _auth_error(request, request.app.state.admin)
    if error is not None:
        return error
    try:
        return _json(_state_payload())
    except Exception:
        log.exception("admin state failed")
        return _json({"error": "unable to load state"}, 500)


async def update_settings(request: Request) -> Response:
    error = _auth_error(request, request.app.state.admin)
    if error is not None:
        return error
    data, error = await _body_json(request)
    if error is not None:
        return error
    if "gateway" in data and isinstance(data["gateway"], dict) and "api_key" in data["gateway"]:
        return _json({"errors": [{"field": "gateway.api_key", "message": "must not be supplied"}]}, 422)
    try:
        settings = Settings.model_validate(data)
    except ValidationError as exc:
        return _json({"errors": _validation_errors(exc)}, 422)
    conn = connect()
    try:
        price_index = load_price_index(conn)
        model_ids = [row["id"] for row in conn.execute("SELECT id FROM models")]
    finally:
        conn.close()
    for model_id, configured in settings.models.per_model.items():
        if configured.enabled and model_id not in price_index:
            return _json({"errors": [{"field": f"models.{model_id}.enabled", "message": "model has no price"}]}, 422)
    if settings.judge.model not in price_index:
        return _json({"errors": [{"field": "judge.model", "message": "model has no price"}]}, 422)
    try:
        settings = Settings.model_validate(settings)
        save_settings(settings)
    except (ValidationError, ValueError) as exc:
        if isinstance(exc, ValidationError):
            errors = _validation_errors(exc)
        else:
            errors = [{"field": "settings", "message": "invalid settings"}]
        return _json({"errors": errors}, 422)
    return _json(_state_payload())


async def update_key(request: Request) -> Response:
    error = _auth_error(request, request.app.state.admin)
    if error is not None:
        return error
    data, error = await _body_json(request)
    if error is not None:
        return error
    key = data.get("key")
    if not isinstance(key, str) or not key:
        return _json({"errors": [{"field": "key", "message": "key is required"}]}, 422)
    save_api_key(key)
    return _json({"key_set": True})


async def connection_test(request: Request) -> Response:
    error = _auth_error(request, request.app.state.admin)
    if error is not None:
        return error
    try:
        result = await test_connection(load_settings())
        return _json({"ok": True, "status": result["status"], "models": result["count"]})
    except Exception as exc:
        status = getattr(getattr(exc, "response", None), "status_code", 0) or 0
        return _json({"ok": False, "status": status, "models": 0, "error": "connection failed"})


async def refresh_models(request: Request) -> Response:
    error = _auth_error(request, request.app.state.admin)
    if error is not None:
        return error
    try:
        settings = load_settings()
        ids = await fetch_models(settings)
        conn = connect()
        try:
            sync_models(conn, ids)
        finally:
            conn.close()
        return _json(_state_payload())
    except Exception:
        return _json({"error": "model refresh failed"}, 502)


def create_app(*, token: str | None = None, clock: Callable[[], float] = time.time) -> Starlette:
    token = os.environ.get("ADMIN_TOKEN") if token is None else token
    if not token or len(token) < 24:
        raise RuntimeError("ADMIN_TOKEN must be set and at least 24 characters")
    admin_state = AdminState(token=token, clock=clock)
    routes = [
        Route("/admin/", index, methods=["GET"]),
        Route("/admin/static/{name:path}", static_file, methods=["GET"]),
        Route("/admin/api/login", login, methods=["POST"]),
        Route("/admin/api/logout", logout, methods=["POST"]),
        Route("/admin/api/state", state, methods=["GET"]),
        Route("/admin/api/settings", update_settings, methods=["PUT"]),
        Route("/admin/api/key", update_key, methods=["PUT"]),
        Route("/admin/api/test", connection_test, methods=["POST"]),
        Route("/admin/api/models/refresh", refresh_models, methods=["POST"]),
    ]
    app = Starlette(routes=routes)
    app.add_middleware(SecurityHeadersMiddleware)
    app.state.admin = admin_state
    return app


def main() -> None:
    uvicorn.run(create_app(), host="127.0.0.1", port=2840)


if __name__ == "__main__":
    main()

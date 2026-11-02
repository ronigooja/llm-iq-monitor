"""Command-line entry point."""

from __future__ import annotations

import argparse
import json
import logging
import sys
from typing import Any

from .settings import Settings, load_settings, save_api_key, save_settings


def _get(settings: Settings, key: str) -> Any:
    value: Any = settings
    for part in key.split("."):
        if part == "api_key":
            return "<set>" if value.gateway.api_key else None
        value = getattr(value, part)
    return value


def _set(settings: Settings, key: str, raw: str) -> None:
    if key == "gateway.api_key":
        raise ValueError("the gateway key can only be set with config set-key")
    import tomllib
    try:
        value = tomllib.loads(f"value = {raw}\n")["value"]
    except Exception:
        value = raw
    parts = key.split(".")
    if key == "ui.sample_max_age_days":
        value = int(value)
    target: Any = settings
    for part in parts[:-1]:
        target = getattr(target, part)
    setattr(target, parts[-1], value)
    Settings.model_validate(settings.model_dump())


def main(argv: list[str] | None = None) -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    parser = argparse.ArgumentParser(prog="llm-iq-monitor")
    sub = parser.add_subparsers(dest="command", required=True)
    config = sub.add_parser("config")
    config.add_argument("action", nargs="?", choices=("show", "get", "set", "set-key"), default=None)
    config.add_argument("key", nargs="?")
    config.add_argument("value", nargs="?")
    sub.add_parser("run")
    manual = sub.add_parser("manual")
    manual.add_argument("models", nargs="+")
    sub.add_parser("migrate")
    sub.add_parser("backup")
    args = parser.parse_args(argv)

    if args.command == "config":
        if args.action is None:
            config.print_help()
            return
        settings = load_settings()
        if args.action == "show":
            print(json.dumps(settings.model_dump(mode="json", exclude={"gateway": {"api_key"}}, exclude_none=True), indent=2))
        elif args.action == "get":
            if not args.key:
                parser.error("config get requires KEY")
            print(json.dumps(_get(settings, args.key)))
        elif args.action == "set":
            if not args.key or args.value is None:
                parser.error("config set requires KEY VALUE")
            _set(settings, args.key, args.value)
            save_settings(settings)
        else:
            save_api_key(sys.stdin.read().rstrip("\r\n"))
        return
    if args.command == "run":
        from .runner_main import serve
        serve()
    elif args.command == "manual":
        from .runner_main import manual
        manual(args.models)
    elif args.command == "migrate":
        from .db import connect
        connect().close()
    elif args.command == "backup":
        from .db import backup, connect
        from .settings import data_dir
        conn = connect()
        print(backup(conn, data_dir() / "backup"))

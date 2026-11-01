"""Configuration models, persistence, and hot reload support."""

from __future__ import annotations

import os
import tomllib
from pathlib import Path
from typing import Any, Awaitable, Callable

import tomli_w
from pydantic import BaseModel, ConfigDict, Field, SecretStr, ValidationError, field_validator, model_validator
from pydantic.networks import AnyHttpUrl
from watchfiles import awatch

DIMS = ("trap", "math", "logic", "code", "instruction", "science")
EFFORTS = ("low", "medium", "high")
DIM_COUNTS = {"trap": 12, "math": 12, "logic": 12, "code": 10, "instruction": 12, "science": 12}


def config_dir() -> Path:
    return Path(os.environ.get("LLM_IQ_CONFIG_DIR", "/etc/llm-iq-monitor"))


def data_dir() -> Path:
    return Path(os.environ.get("LLM_IQ_DATA_DIR", "/var/lib/llm-iq-monitor"))


def _cron(value: str) -> str:
    from apscheduler.triggers.cron import CronTrigger

    try:
        CronTrigger.from_crontab(value, timezone="UTC")
    except (ValueError, TypeError) as exc:
        raise ValueError("must be a valid five-field cron expression") from exc
    return value


class Gateway(BaseModel):
    base_url: str = "https://ai.nodemgr.uk/v1"
    models_url: str | None = None
    api_key: SecretStr | None = Field(default=None, exclude=True, repr=False)

    @field_validator("base_url", "models_url")
    @classmethod
    def valid_url(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return str(AnyHttpUrl(value))

    @model_validator(mode="after")
    def default_models_url(self) -> "Gateway":
        if self.models_url is None:
            self.models_url = str(self.base_url).rstrip("/") + "/models"
        return self


class Schedule(BaseModel):
    heartbeat_cron: str = "0 * * * *"

    @field_validator("heartbeat_cron")
    @classmethod
    def valid_cron(cls, value: str) -> str:
        return _cron(value)


class Prices(BaseModel):
    url: str = "https://models.dev/api.json"
    refresh_cron: str = "30 3 * * *"

    @field_validator("url")
    @classmethod
    def valid_url(cls, value: str) -> str:
        return str(AnyHttpUrl(value))

    @field_validator("refresh_cron")
    @classmethod
    def valid_cron(cls, value: str) -> str:
        return _cron(value)


class ModelSettings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    enabled: bool = False
    interval_h: int | None = Field(default=None, ge=1)
    dims: list[str] | None = None
    efforts: list[str] | None = None

    @field_validator("dims")
    @classmethod
    def valid_dims(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (not value or any(item not in DIMS for item in value) or len(set(value)) != len(value)):
            raise ValueError(f"dims must contain unique values from {DIMS}")
        return value

    @field_validator("efforts")
    @classmethod
    def valid_efforts(cls, value: list[str] | None) -> list[str] | None:
        if value is not None and (not value or any(item not in EFFORTS for item in value) or len(set(value)) != len(value)):
            raise ValueError(f"efforts must contain unique values from {EFFORTS}")
        return value

    @model_validator(mode="after")
    def enabled_has_choices(self) -> "ModelSettings":
        if self.enabled and (self.dims is not None and not self.dims or self.efforts is not None and not self.efforts):
            raise ValueError("an enabled model must have non-empty dims and efforts")
        return self


class Models(BaseModel):
    default_interval_h: int = Field(default=6, ge=1)
    default_dims: list[str] = Field(default_factory=lambda: list(DIMS))
    default_efforts: list[str] = Field(default_factory=lambda: ["medium"])
    per_model: dict[str, ModelSettings] = Field(default_factory=dict, alias="per_model")

    @model_validator(mode="before")
    @classmethod
    def collect_model_tables(cls, value: Any) -> Any:
        if not isinstance(value, dict):
            return value
        value = dict(value)
        known = {"default_interval_h", "default_dims", "default_efforts", "per_model"}
        models = dict(value.get("per_model", {}))
        for key in list(value):
            if key not in known:
                models[key] = value.pop(key)
        value["per_model"] = models
        return value

    @field_validator("default_dims")
    @classmethod
    def valid_default_dims(cls, value: list[str]) -> list[str]:
        if not value or any(item not in DIMS for item in value) or len(set(value)) != len(value):
            raise ValueError(f"default_dims must contain unique values from {DIMS}")
        return value

    @field_validator("default_efforts")
    @classmethod
    def valid_default_efforts(cls, value: list[str]) -> list[str]:
        if not value or any(item not in EFFORTS for item in value) or len(set(value)) != len(value):
            raise ValueError(f"default_efforts must contain unique values from {EFFORTS}")
        return value


class Run(BaseModel):
    parallel_models: int = Field(default=3, ge=1, le=8)
    timeout_s: int = Field(default=600, ge=1)
    max_tokens: int = Field(default=16384, ge=1)


class Net(BaseModel):
    rtt_fallback_ms: int = Field(default=30, ge=0)


class Retention(BaseModel):
    reply_days: int = Field(default=14, ge=0)


class Settings(BaseModel):
    model_config = ConfigDict(extra="forbid")
    gateway: Gateway = Field(default_factory=Gateway)
    schedule: Schedule = Field(default_factory=Schedule)
    prices: Prices = Field(default_factory=Prices)
    models: Models = Field(default_factory=Models)
    run: Run = Field(default_factory=Run)
    net: Net = Field(default_factory=Net)
    retention: Retention = Field(default_factory=Retention)

    def effective(self, model_id: str) -> ModelSettings:
        configured = self.models.per_model.get(model_id, ModelSettings())
        if isinstance(configured, dict):
            configured = ModelSettings.model_validate(configured)
        return ModelSettings(
            enabled=configured.enabled,
            interval_h=configured.interval_h or self.models.default_interval_h,
            dims=configured.dims if configured.dims is not None else list(self.models.default_dims),
            efforts=configured.efforts if configured.efforts is not None else list(self.models.default_efforts),
        )


def _secret_path() -> Path:
    return config_dir() / "secrets.env"


def _read_secret() -> SecretStr | None:
    value = os.environ.get("GATEWAY_API_KEY")
    if value is None:
        try:
            for line in _secret_path().read_text().splitlines():
                if line.startswith("GATEWAY_API_KEY="):
                    value = line.partition("=")[2]
                    break
        except FileNotFoundError:
            pass
    return SecretStr(value) if value else None


def load_settings() -> Settings:
    path = config_dir() / "settings.toml"
    raw: dict[str, Any] = {}
    if path.exists():
        with path.open("rb") as stream:
            raw = tomllib.load(stream)
    settings = Settings.model_validate(raw)
    settings.gateway.api_key = _read_secret()
    return settings


def save_settings(settings: Settings) -> None:
    target = config_dir()
    target.mkdir(parents=True, exist_ok=True)
    data = settings.model_dump(mode="json", exclude={"gateway": {"api_key"}}, exclude_none=True)
    # The public TOML shape uses [models."model-id"], not an extra per_model table.
    model_data = data["models"].pop("per_model", {})
    for model_id, model_settings in model_data.items():
        data["models"][model_id] = model_settings
    (target / "settings.toml").write_text(tomli_w.dumps(data), encoding="utf-8")


def save_api_key(value: str) -> None:
    target = config_dir()
    target.mkdir(parents=True, exist_ok=True)
    path = _secret_path()
    path.write_text(f"GATEWAY_API_KEY={value}\n", encoding="utf-8")
    path.chmod(0o600)


async def watch_settings(callback: Callable[[Settings], Any] | Callable[[Settings], Awaitable[Any]]) -> None:
    """Watch settings.toml and call back only after a complete valid parse."""
    config_dir().mkdir(parents=True, exist_ok=True)
    async for changes in awatch(config_dir()):
        if any(Path(path).name == "settings.toml" for _, path in changes):
            try:
                value = load_settings()
            except (OSError, ValidationError, ValueError, tomllib.TOMLDecodeError):
                continue
            result = callback(value)
            if hasattr(result, "__await__"):
                await result

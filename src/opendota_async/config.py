"""Client configuration with environment overrides (``OPENDOTA_*``)."""

from __future__ import annotations

import logging
import os
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr, model_validator

logger = logging.getLogger("opendota_async.config")

_ENV_PREFIX = "OPENDOTA_"


def _env_bool(key: str) -> bool | None:
    v = os.environ.get(key)
    if v is None:
        return None
    return v.strip().lower() in {"1", "true", "yes", "on"}


def _env_int(key: str) -> int | None:
    v = os.environ.get(key)
    if v is None or not v.strip():
        return None
    try:
        return int(v)
    except ValueError:
        logger.warning("Ignoring invalid int for %s=%r", key, v)
        return None


def _env_float(key: str) -> float | None:
    v = os.environ.get(key)
    if v is None or not v.strip():
        return None
    try:
        return float(v)
    except ValueError:
        logger.warning("Ignoring invalid float for %s=%r", key, v)
        return None


def _env_str(key: str) -> str | None:
    v = os.environ.get(key)
    if v is None:
        return None
    s = v.strip()
    return s or None


class OpenDotaClientConfig(BaseModel):
    """Serializable HTTP client settings.

    Environment variables use the prefix ``OPENDOTA_`` (for example ``OPENDOTA_BASE_URL``).
    Values you pass explicitly to the constructor take precedence; when a field is filled
    from the environment, an INFO log line records the variable name (not secrets).
    """

    model_config = ConfigDict(extra="forbid", validate_assignment=True)

    base_url: str = Field(default="https://api.opendota.com/api")
    timeout: float | tuple[float, float] | None = Field(default=30.0)
    pool_connections: int = Field(default=10, ge=1)
    pool_maxsize: int = Field(default=10, ge=1)
    retries: int | Any = Field(
        default=3,
        description="Niquests transport retries (int or urllib3 Retry)",
    )
    auth: Any | None = Field(default=None, repr=False)
    user_agent: str | None = Field(default=None)
    proxies: dict[str, str] | None = None
    verify: bool | str = True
    happy_eyeballs: bool | int = False
    keepalive_delay: float | int | None = 600.0
    keepalive_idle_window: float | int | None = 60.0
    multiplexed: bool = Field(
        default=False,
        description=(
            "Enable HTTP/2+ lazy multiplexing on the session. "
            "Turn on for gather(); keep off for normal JSON calls."
        ),
    )
    disable_http2: bool = False
    disable_http3: bool = False
    revocation_configuration: Any | None = Field(default=None, repr=False)

    api_key: str | None = Field(default=None, repr=False)
    bearer_token: str | None = Field(default=None, repr=False)

    rate_limit_rps: float | None = Field(
        default=30.0,
        description="AsyncLeakyBucketLimiter rate (requests/sec); None disables hook limiter.",
    )
    max_concurrency: int = Field(default=32, ge=1)

    retry_max_attempts: int = Field(default=5, ge=1)
    retry_max_total_seconds: float = Field(default=60.0, ge=0.0)
    retry_post: bool = False

    _logged_env: bool = PrivateAttr(default=False)

    @model_validator(mode="after")
    def _check_pool(self) -> OpenDotaClientConfig:
        if self.pool_maxsize < self.pool_connections:
            msg = (
                f"pool_maxsize ({self.pool_maxsize}) must be >= "
                f"pool_connections ({self.pool_connections})"
            )
            raise ValueError(msg)
        return self

    @classmethod
    def from_env(cls, **overrides: Any) -> OpenDotaClientConfig:
        """Load defaults from ``OPENDOTA_*`` environment variables, then apply ``overrides``."""
        data: dict[str, Any] = {}
        logged: list[str] = []

        if (base_url := _env_str(f"{_ENV_PREFIX}BASE_URL")) is not None:
            data["base_url"] = base_url
            logged.append("OPENDOTA_BASE_URL")
        if (timeout := _env_float(f"{_ENV_PREFIX}TIMEOUT")) is not None:
            data["timeout"] = timeout
            logged.append("OPENDOTA_TIMEOUT")
        if (pool_c := _env_int(f"{_ENV_PREFIX}POOL_CONNECTIONS")) is not None:
            data["pool_connections"] = pool_c
            logged.append("OPENDOTA_POOL_CONNECTIONS")
        if (pool_m := _env_int(f"{_ENV_PREFIX}POOL_MAXSIZE")) is not None:
            data["pool_maxsize"] = pool_m
            logged.append("OPENDOTA_POOL_MAXSIZE")
        if (retries := _env_int(f"{_ENV_PREFIX}RETRIES")) is not None:
            data["retries"] = retries
            logged.append("OPENDOTA_RETRIES")
        if (ua := _env_str(f"{_ENV_PREFIX}USER_AGENT")) is not None:
            data["user_agent"] = ua
            logged.append("OPENDOTA_USER_AGENT")
        if (verify := _env_bool(f"{_ENV_PREFIX}VERIFY")) is not None:
            data["verify"] = verify
            logged.append("OPENDOTA_VERIFY")
        if (mult := _env_bool(f"{_ENV_PREFIX}MULTIPLEXED")) is not None:
            data["multiplexed"] = mult
            logged.append("OPENDOTA_MULTIPLEXED")
        if (dh2 := _env_bool(f"{_ENV_PREFIX}DISABLE_HTTP2")) is not None:
            data["disable_http2"] = dh2
            logged.append("OPENDOTA_DISABLE_HTTP2")
        if (dh3 := _env_bool(f"{_ENV_PREFIX}DISABLE_HTTP3")) is not None:
            data["disable_http3"] = dh3
            logged.append("OPENDOTA_DISABLE_HTTP3")
        if (apk := _env_str(f"{_ENV_PREFIX}API_KEY")) is not None:
            data["api_key"] = apk
            logged.append("OPENDOTA_API_KEY")
        if (bt := _env_str(f"{_ENV_PREFIX}BEARER_TOKEN")) is not None:
            data["bearer_token"] = bt
            logged.append("OPENDOTA_BEARER_TOKEN")
        if (rps := _env_float(f"{_ENV_PREFIX}RATE_LIMIT_RPS")) is not None:
            data["rate_limit_rps"] = rps
            logged.append("OPENDOTA_RATE_LIMIT_RPS")
        if _env_bool(f"{_ENV_PREFIX}RATE_LIMIT_DISABLED") is True:
            data["rate_limit_rps"] = None
            logged.append("OPENDOTA_RATE_LIMIT_DISABLED")
        if (mxc := _env_int(f"{_ENV_PREFIX}MAX_CONCURRENCY")) is not None:
            data["max_concurrency"] = mxc
            logged.append("OPENDOTA_MAX_CONCURRENCY")

        base = cls(**data)
        merged = base.model_copy(update=overrides, deep=True)
        if logged:
            logger.info(
                "Applied environment configuration from: %s",
                ", ".join(sorted(logged)),
            )
        merged._logged_env = True
        return merged

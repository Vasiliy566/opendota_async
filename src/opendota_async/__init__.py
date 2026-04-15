"""Async OpenDota API client built on Niquests."""

from opendota_async.client import OpenDotaClient
from opendota_async.config import OpenDotaClientConfig
from opendota_async.errors import (
    APIError,
    AuthenticationError,
    BadRequestError,
    ConflictError,
    ConnectionError,
    ForbiddenError,
    NotFoundError,
    OpenDotaError,
    RateLimitError,
    ServerError,
    TimeoutError,
    UnprocessableError,
    ValidationError,
)
from opendota_async.sync_client import OpenDotaSyncClient

__version__ = "0.1.0"

__all__ = [
    "APIError",
    "AuthenticationError",
    "BadRequestError",
    "ConflictError",
    "ConnectionError",
    "ForbiddenError",
    "NotFoundError",
    "OpenDotaClient",
    "OpenDotaClientConfig",
    "OpenDotaError",
    "OpenDotaSyncClient",
    "RateLimitError",
    "ServerError",
    "TimeoutError",
    "UnprocessableError",
    "ValidationError",
    "__version__",
]

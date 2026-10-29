"""Validated environment configuration for the API."""

import os
from urllib.parse import urlsplit

DEFAULT_CORS_ORIGINS = (
    "http://localhost:5173",
    "http://127.0.0.1:5173",
)
_SUPPORTED_ENVIRONMENTS = {"development", "test", "staging", "production"}


def get_cors_origins() -> list[str]:
    """Return explicit CORS origins, requiring them in production."""
    environment = os.getenv("CARBONGUARD_ENVIRONMENT", "development").strip().lower()
    if environment not in _SUPPORTED_ENVIRONMENTS:
        raise RuntimeError("CARBONGUARD_ENVIRONMENT has an unsupported value")

    configured_origins = os.getenv("CARBONGUARD_CORS_ORIGINS")
    if configured_origins is None:
        if environment == "production":
            raise RuntimeError(
                "CARBONGUARD_CORS_ORIGINS must be configured in production"
            )
        return list(DEFAULT_CORS_ORIGINS)

    origins = list(
        dict.fromkeys(
            origin.strip().rstrip("/")
            for origin in configured_origins.split(",")
            if origin.strip()
        )
    )
    if not origins:
        raise RuntimeError("CARBONGUARD_CORS_ORIGINS must contain an origin")

    for origin in origins:
        parsed = urlsplit(origin)
        try:
            parsed.port
        except ValueError as exc:
            raise RuntimeError(
                "CARBONGUARD_CORS_ORIGINS contains an invalid port"
            ) from exc
        if (
            origin == "*"
            or parsed.scheme not in {"http", "https"}
            or not parsed.netloc
            or not parsed.hostname
            or "*" in parsed.hostname
            or parsed.username is not None
            or parsed.password is not None
            or parsed.path
            or parsed.query
            or parsed.fragment
        ):
            raise RuntimeError(
                "CARBONGUARD_CORS_ORIGINS must contain comma-separated "
                "HTTP(S) origins without paths"
            )
    return origins

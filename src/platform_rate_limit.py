# -*- coding: utf-8 -*-
"""Small in-process rate limiter for platform write endpoints."""

from __future__ import annotations

import os
import time
from threading import Lock
from typing import Any, Dict, Tuple

from fastapi import Request
from fastapi.responses import JSONResponse

from src.auth import get_client_ip


_BucketKey = Tuple[str, str, str]
_buckets: Dict[_BucketKey, list[float]] = {}
_lock = Lock()


def _truthy_env(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    try:
        value = int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default
    return max(1, value)


def _scope_env_name(scope: str) -> str:
    return "PLATFORM_RATE_LIMIT_" + "".join(ch if ch.isalnum() else "_" for ch in scope.upper()) + "_MAX"


def _limit_for_scope(scope: str) -> int:
    return _int_env(_scope_env_name(scope), _int_env("PLATFORM_RATE_LIMIT_DEFAULT_MAX", 120))


def _identity_for_request(request: Request, user_id: int | None) -> str:
    if user_id is not None:
        return f"user:{int(user_id)}"
    return f"ip:{get_client_ip(request)}"


def reset_platform_rate_limits() -> None:
    """Clear limiter state for isolated tests and local verifier reruns."""

    with _lock:
        _buckets.clear()


def check_platform_rate_limit(
    request: Request,
    scope: str,
    *,
    user_id: int | None = None,
) -> JSONResponse | None:
    """Return a 429 response when the request exceeds the configured bucket.

    Buckets are scoped by database path so unit tests using temporary databases
    cannot poison each other while the process stays alive.
    """

    if not _truthy_env("PLATFORM_RATE_LIMIT_ENABLED", "false"):
        return None

    window_seconds = _int_env("PLATFORM_RATE_LIMIT_WINDOW_SECONDS", 60)
    max_requests = _limit_for_scope(scope)
    now = time.monotonic()
    cutoff = now - window_seconds
    key: _BucketKey = (
        os.getenv("DATABASE_PATH", ""),
        scope,
        _identity_for_request(request, user_id),
    )

    with _lock:
        hits = [timestamp for timestamp in _buckets.get(key, []) if timestamp > cutoff]
        if len(hits) >= max_requests:
            oldest = min(hits) if hits else now
            retry_after = max(1, int(round(window_seconds - (now - oldest))))
            _buckets[key] = hits
            return JSONResponse(
                status_code=429,
                content={
                    "error": "rate_limited",
                    "message": "Too many requests. Please wait before trying again.",
                    "retry_after_seconds": retry_after,
                },
            )
        hits.append(now)
        _buckets[key] = hits
    return None

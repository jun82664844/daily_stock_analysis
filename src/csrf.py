# -*- coding: utf-8 -*-
"""CSRF helpers for cookie-authenticated browser sessions."""

from __future__ import annotations

import os
import secrets
from typing import Any

from fastapi import HTTPException, Request
from fastapi.responses import Response

CSRF_COOKIE_NAME = "dsa_csrf_token"
CSRF_HEADER_NAME = "X-DSA-CSRF"
UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


def csrf_enabled() -> bool:
    return os.getenv("PLATFORM_CSRF_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def generate_csrf_token() -> str:
    return secrets.token_urlsafe(32)


def set_csrf_cookie(response: Response, *, secure: bool, max_age: int) -> None:
    response.set_cookie(
        key=CSRF_COOKIE_NAME,
        value=generate_csrf_token(),
        httponly=False,
        samesite="lax",
        secure=secure,
        path="/",
        max_age=max_age,
    )


def delete_csrf_cookie(response: Response) -> None:
    response.delete_cookie(key=CSRF_COOKIE_NAME, path="/")


def require_csrf(request: Request) -> None:
    if not csrf_enabled():
        return
    cookie_value = request.cookies.get(CSRF_COOKIE_NAME)
    header_value = request.headers.get(CSRF_HEADER_NAME)
    if not cookie_value or not header_value or not secrets.compare_digest(cookie_value, header_value):
        raise HTTPException(
            status_code=403,
            detail={"error": "csrf_failed", "message": "CSRF token missing or invalid"},
        )


def csrf_error_detail(exc: HTTPException) -> dict[str, Any]:
    if isinstance(exc.detail, dict):
        return exc.detail
    return {"error": "csrf_failed", "message": str(exc.detail)}

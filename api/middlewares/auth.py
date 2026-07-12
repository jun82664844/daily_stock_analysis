# -*- coding: utf-8 -*-
"""
Auth middleware: protect /api/v1/* when admin auth is enabled.
"""

from __future__ import annotations

import logging
import re
from typing import Callable

from fastapi import HTTPException
from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

from src.auth import COOKIE_NAME, is_auth_enabled, verify_session
from src.csrf import UNSAFE_METHODS, csrf_enabled, csrf_error_detail, require_csrf
from src.platform_accounts import (
    PLATFORM_SESSION_COOKIE,
    is_platform_user_auth_enabled,
    verify_platform_session,
)

logger = logging.getLogger(__name__)

EXEMPT_PATHS = frozenset({
    "/api/v1/auth/login",
    "/api/v1/auth/status",
    "/api/v1/platform/login",
    "/api/v1/platform/register",
    "/api/v1/platform/register/verification-code",
    "/api/v1/platform/retention/events",
    "/api/v1/platform/status",
    "/api/v1/platform/local-model/status",
    "/api/v1/billing/webhook",
    "/api/health",
    "/api/v1/health",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
})

PLATFORM_USER_PATH_PREFIXES = (
    "/api/v1/platform/",
    "/api/v1/analysis/",
    "/api/v1/stocks/",
    "/api/v1/billing/",
    "/api/v1/history",
)


def _path_exempt(path: str) -> bool:
    """Check if path is exempt from auth."""
    normalized = path.rstrip("/") or "/"
    return normalized in EXEMPT_PATHS


def _platform_user_path(path: str) -> bool:
    return any(path.startswith(prefix) for prefix in PLATFORM_USER_PATH_PREFIXES)


def _public_no_ai_query_path(request: Request) -> bool:
    """Allow anonymous users to try public no-AI stock research paths."""
    if request.method.upper() != "GET":
        return False
    path = request.url.path.rstrip("/")
    return re.fullmatch(
        r"/api/v1/stocks/[^/]+/(?:snapshot|history|kronos-forecast|research-workflows)",
        path,
    ) is not None


def _public_market_screening_path(request: Request) -> bool:
    """Expose information-only screening while keeping install/config writes protected."""
    method = request.method.upper()
    path = request.url.path.rstrip("/")
    if method == "GET":
        return (
            path in {
                "/api/v1/alphasift/status",
                "/api/v1/alphasift/strategies",
                "/api/v1/alphasift/hotspots",
            }
            or path.startswith("/api/v1/alphasift/hotspots/")
            or path.startswith("/api/v1/alphasift/screen/tasks/")
        )
    return method == "POST" and path in {
        "/api/v1/alphasift/screen",
        "/api/v1/alphasift/screen/tasks",
    }


def _csrf_failure_response(request: Request) -> JSONResponse | None:
    if not csrf_enabled() or request.method.upper() not in UNSAFE_METHODS:
        return None
    try:
        require_csrf(request)
    except HTTPException as exc:
        return JSONResponse(status_code=exc.status_code, content=csrf_error_detail(exc))
    return None


class AuthMiddleware(BaseHTTPMiddleware):
    """Require valid session for /api/v1/* when auth is enabled."""

    async def dispatch(
        self,
        request: Request,
        call_next: Callable,
    ):
        admin_auth_enabled = is_auth_enabled()
        platform_auth_enabled = is_platform_user_auth_enabled()

        if not admin_auth_enabled and not platform_auth_enabled:
            return await call_next(request)

        path = request.url.path
        if _path_exempt(path):
            return await call_next(request)

        if not path.startswith("/api/v1/"):
            return await call_next(request)

        if _public_no_ai_query_path(request) or _public_market_screening_path(request):
            return await call_next(request)

        admin_cookie_val = request.cookies.get(COOKIE_NAME)
        if admin_auth_enabled and admin_cookie_val and verify_session(admin_cookie_val):
            csrf_response = _csrf_failure_response(request)
            if csrf_response is not None:
                return csrf_response
            return await call_next(request)

        if platform_auth_enabled and _platform_user_path(path):
            platform_cookie_val = request.cookies.get(PLATFORM_SESSION_COOKIE)
            if platform_cookie_val and verify_platform_session(platform_cookie_val):
                csrf_response = _csrf_failure_response(request)
                if csrf_response is not None:
                    return csrf_response
                return await call_next(request)

        return JSONResponse(
            status_code=401,
            content={
                "error": "unauthorized",
                "message": "Login required",
            },
        )


def add_auth_middleware(app):
    """Add auth middleware to protect API routes.

    The middleware is always registered; whether auth is enforced is determined
    at request time by is_auth_enabled() so the decision stays consistent across
    any runtime configuration reload.
    """
    app.add_middleware(AuthMiddleware)

# -*- coding: utf-8 -*-
"""Public platform account endpoints."""

from __future__ import annotations

import os
from typing import Any, Dict, List

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, Response
from sqlalchemy.exc import IntegrityError

from src.auth import (
    COOKIE_NAME,
    check_rate_limit,
    clear_rate_limit,
    get_client_ip,
    record_login_failure,
    verify_session,
)
from api.v1.schemas.platform import (
    PlatformApiKeyItem,
    PlatformApiKeyUpsertRequest,
    PlatformAuthResponse,
    PlatformLoginRequest,
    PlatformPlanUpdateRequest,
    PlatformQuotaResponse,
    PlatformRegisterRequest,
    PlatformStatusResponse,
    PlatformUserResponse,
    PlatformWatchlistRefreshResponse,
    PlatformWatchlistResponse,
    PlatformWatchlistUpsertRequest,
)
from src.platform_accounts import (
    PLATFORM_SESSION_COOKIE,
    PLATFORM_SESSION_MAX_AGE_HOURS_DEFAULT,
    InvalidCredentials,
    PlatformAccountService,
    PlatformIdentity,
    create_platform_session,
    is_platform_user_auth_enabled,
    platform_identity_from_request,
)
from src.platform_audit import PlatformAuditLogger
from src.platform_rate_limit import check_platform_rate_limit
from src.platform_watchlist import PlatformWatchlistService
from src.services.local_functional_status import build_local_functional_status
from src.csrf import (
    CSRF_COOKIE_NAME as PLATFORM_CSRF_COOKIE,
    CSRF_HEADER_NAME as PLATFORM_CSRF_HEADER,
    csrf_enabled as _csrf_enabled,
    delete_csrf_cookie,
    require_csrf,
    set_csrf_cookie,
)


router = APIRouter()


def _audit(*, user_id: int | None, action: str, metadata: Dict[str, Any] | None = None) -> None:
    try:
        PlatformAuditLogger().record(user_id=user_id, action=action, metadata=metadata or {})
    except Exception:
        pass


def _cookie_params(request: Request) -> Dict[str, Any]:
    secure = False
    if os.getenv("TRUST_X_FORWARDED_FOR", "false").strip().lower() == "true":
        secure = request.headers.get("X-Forwarded-Proto", "").lower() == "https"
    else:
        secure = request.url.scheme == "https"
    try:
        max_age_hours = int(
            os.getenv("PLATFORM_SESSION_MAX_AGE_HOURS", str(PLATFORM_SESSION_MAX_AGE_HOURS_DEFAULT))
        )
    except ValueError:
        max_age_hours = PLATFORM_SESSION_MAX_AGE_HOURS_DEFAULT
    return {
        "httponly": True,
        "samesite": "lax",
        "secure": secure,
        "path": "/",
        "max_age": max_age_hours * 3600,
    }


def _set_platform_cookie(response: Response, session_value: str, request: Request) -> None:
    params = _cookie_params(request)
    response.set_cookie(
        key=PLATFORM_SESSION_COOKIE,
        value=session_value,
        **params,
    )
    if _csrf_enabled():
        set_csrf_cookie(response, secure=bool(params["secure"]), max_age=int(params["max_age"]))


def _require_platform_csrf(request: Request) -> None:
    require_csrf(request)


def _user_payload(user: Any) -> Dict[str, Any]:
    return {
        "id": int(user.id),
        "email": user.email,
        "role": user.role,
        "plan": user.plan,
        "status": user.status,
    }


def _auth_payload(service: PlatformAccountService, user: Any) -> Dict[str, Any]:
    return {
        "user": _user_payload(user),
        "quota": service.get_quota_status(int(user.id)),
    }


def _account_payload(service: PlatformAccountService, user: Any) -> Dict[str, Any]:
    buckets = ("basic_query", "ai_quick", "ai_quick_user_key", "ai_deep", "ai_deep_user_key", "ai_local", "market_review")
    api_keys = service.list_api_keys(int(user.id))
    if any(item.get("enabled") for item in api_keys):
        recommended_query_mode = "user"
    elif os.getenv("LOCAL_LLM_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}:
        recommended_query_mode = "local"
    else:
        recommended_query_mode = "platform"
    return {
        **_auth_payload(service, user),
        "quota_buckets": [service.get_feature_quota_status(int(user.id), bucket) for bucket in buckets],
        "api_keys": api_keys,
        "recommended_query_mode": recommended_query_mode,
    }


def _require_identity(request: Request) -> PlatformIdentity:
    identity = platform_identity_from_request(request)
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})
    return identity


def _require_admin_identity(request: Request) -> PlatformIdentity:
    admin_cookie = request.cookies.get(COOKIE_NAME)
    if admin_cookie and verify_session(admin_cookie):
        return PlatformIdentity(
            user_id=None,
            email="admin",
            role="admin",
            plan="enterprise",
            is_admin=True,
        )

    identity = _require_identity(request)
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Admin role required"})
    return identity


@router.get("/status", response_model=PlatformStatusResponse)
async def platform_status() -> Dict[str, bool]:
    return {"platform_auth_enabled": is_platform_user_auth_enabled()}


@router.post("/register", response_model=PlatformAuthResponse)
async def platform_register(request: Request, body: PlatformRegisterRequest):
    if not is_platform_user_auth_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "platform_auth_disabled", "message": "Platform user auth is disabled"},
        )
    limited = check_platform_rate_limit(request, "register")
    if limited is not None:
        return limited

    service = PlatformAccountService()
    try:
        user = service.create_user(body.email, body.password)
    except IntegrityError:
        return JSONResponse(status_code=409, content={"error": "email_exists", "message": "Email already exists"})
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_request", "message": str(exc)})

    resp = JSONResponse(content=_auth_payload(service, user))
    _set_platform_cookie(resp, create_platform_session(user), request)
    return resp


@router.post("/login", response_model=PlatformAuthResponse)
async def platform_login(request: Request, body: PlatformLoginRequest):
    if not is_platform_user_auth_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "platform_auth_disabled", "message": "Platform user auth is disabled"},
        )

    ip = get_client_ip(request)
    if not check_rate_limit(ip):
        return JSONResponse(
            status_code=429,
            content={
                "error": "rate_limited",
                "message": "Too many failed attempts. Please try again later.",
            },
        )

    service = PlatformAccountService()
    try:
        user = service.verify_login(body.email, body.password)
    except InvalidCredentials:
        record_login_failure(ip)
        _audit(user_id=None, action="platform_login_failed", metadata={"email": body.email})
        return JSONResponse(status_code=401, content={"error": "invalid_credentials", "message": "Invalid login"})

    clear_rate_limit(ip)
    _audit(user_id=int(user.id), action="platform_login_success", metadata={"email": user.email})
    resp = JSONResponse(content=_auth_payload(service, user))
    _set_platform_cookie(resp, create_platform_session(user), request)
    return resp


@router.post("/logout")
async def platform_logout():
    resp = Response(status_code=204)
    resp.delete_cookie(key=PLATFORM_SESSION_COOKIE, path="/")
    delete_csrf_cookie(resp)
    return resp


@router.get("/me", response_model=PlatformAuthResponse)
async def platform_me(request: Request):
    identity = _require_identity(request)
    service = PlatformAccountService()
    user = service.get_user(int(identity.user_id))
    if user is None:
        return JSONResponse(status_code=401, content={"error": "unauthorized", "message": "Login required"})
    return _auth_payload(service, user)


@router.get("/account")
async def platform_account(request: Request):
    identity = _require_identity(request)
    service = PlatformAccountService()
    user = service.get_user(int(identity.user_id))
    if user is None:
        return JSONResponse(status_code=401, content={"error": "unauthorized", "message": "Login required"})
    return _account_payload(service, user)


@router.get("/quota", response_model=PlatformQuotaResponse)
async def platform_quota(request: Request):
    identity = _require_identity(request)
    return PlatformAccountService().get_quota_status(int(identity.user_id))


@router.get("/watchlist", response_model=PlatformWatchlistResponse)
async def platform_watchlist(request: Request):
    identity = _require_identity(request)
    return PlatformWatchlistService().list_items(int(identity.user_id))


@router.post("/watchlist", response_model=PlatformWatchlistResponse)
async def platform_watchlist_add(request: Request, body: PlatformWatchlistUpsertRequest):
    _require_platform_csrf(request)
    identity = _require_identity(request)
    limited = check_platform_rate_limit(request, "watchlist", user_id=int(identity.user_id))
    if limited is not None:
        return limited
    try:
        result = PlatformWatchlistService().add_item(int(identity.user_id), body.stock_code)
        _audit(
            user_id=int(identity.user_id),
            action="watchlist_item_added",
            metadata={"stock_code": body.stock_code},
        )
        return result
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_stock_code", "message": str(exc)})


@router.delete("/watchlist/{stock_code}", response_model=PlatformWatchlistResponse)
async def platform_watchlist_remove(request: Request, stock_code: str):
    _require_platform_csrf(request)
    identity = _require_identity(request)
    limited = check_platform_rate_limit(request, "watchlist", user_id=int(identity.user_id))
    if limited is not None:
        return limited
    try:
        result = PlatformWatchlistService().remove_item(int(identity.user_id), stock_code)
        _audit(
            user_id=int(identity.user_id),
            action="watchlist_item_removed",
            metadata={"stock_code": stock_code},
        )
        return result
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_stock_code", "message": str(exc)})


@router.post("/watchlist/refresh", response_model=PlatformWatchlistRefreshResponse)
async def platform_watchlist_refresh(request: Request):
    identity = _require_identity(request)
    return PlatformWatchlistService().refresh(int(identity.user_id))


@router.get("/api-keys", response_model=List[PlatformApiKeyItem])
async def platform_list_api_keys(request: Request):
    identity = _require_identity(request)
    return PlatformAccountService().list_api_keys(int(identity.user_id))


@router.post("/api-keys", response_model=PlatformApiKeyItem)
async def platform_store_api_key(request: Request, body: PlatformApiKeyUpsertRequest):
    _require_platform_csrf(request)
    identity = _require_identity(request)
    limited = check_platform_rate_limit(request, "api_keys", user_id=int(identity.user_id))
    if limited is not None:
        return limited
    try:
        item = PlatformAccountService().store_api_key(
            int(identity.user_id),
            provider=body.provider,
            api_key=body.api_key,
            model=body.model,
        )
        _audit(
            user_id=int(identity.user_id),
            action="api_key_saved",
            metadata={"provider": body.provider, "model": body.model, "api_key": body.api_key},
        )
        return item
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_api_key", "message": str(exc)})


@router.get("/admin/users")
async def platform_admin_list_users(request: Request):
    identity = _require_admin_identity(request)
    _audit(user_id=identity.user_id, action="admin_user_list_viewed", metadata={})
    users = PlatformAccountService().list_users()
    return {"users": [_user_payload(user) for user in users]}


@router.get("/admin/usage")
async def platform_admin_usage(request: Request):
    identity = _require_admin_identity(request)
    _audit(user_id=identity.user_id, action="admin_usage_viewed", metadata={})
    service = PlatformAccountService()
    users = service.list_users(limit=500)
    buckets = ("ai_quick", "ai_quick_user_key", "ai_deep", "ai_deep_user_key", "ai_local", "market_review")
    usage = []
    for user in users:
        for bucket in buckets:
            status = service.get_feature_quota_status(int(user.id), bucket)
            if status["used"] <= 0:
                continue
            usage.append(
                {
                    "user_id": int(user.id),
                    "email": user.email,
                    "plan": user.plan,
                    "quota_bucket": bucket,
                    "used": status["used"],
                    "weekly_limit": status["weekly_limit"],
                    "remaining": status["remaining"],
                    "period_start": status["period_start"],
                }
            )
    audit_events = PlatformAuditLogger().list_events(limit=100)
    return {"usage": usage, "audit_events": audit_events}


@router.get("/admin/local-status")
async def platform_admin_local_status(request: Request):
    identity = _require_admin_identity(request)
    _audit(user_id=identity.user_id, action="admin_local_status_viewed", metadata={})
    return build_local_functional_status()


@router.patch("/admin/users/{user_id}/plan", response_model=PlatformAuthResponse)
async def platform_admin_update_user_plan(request: Request, user_id: int, body: PlatformPlanUpdateRequest):
    _require_platform_csrf(request)
    identity = _require_admin_identity(request)
    service = PlatformAccountService()
    try:
        user = service.set_user_plan(user_id, body.plan)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": "invalid_plan", "message": str(exc)})
    _audit(
        user_id=identity.user_id,
        action="plan_changed",
        metadata={"target_user_id": user_id, "plan": body.plan},
    )
    return _auth_payload(service, user)

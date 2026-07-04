# -*- coding: utf-8 -*-
"""Billing boundary endpoints.

Local V1 keeps billing disabled while preserving the route contract and
webhook signature gate required before public launch.
"""

from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse

from api.v1.schemas.billing import CheckoutRequest
from src.auth import COOKIE_NAME, verify_session
from src.billing.lifecycle import BillingLifecycleService
from src.billing.payment_provider import SandboxPaymentProvider
from src.csrf import require_csrf
from src.platform_accounts import PlatformAccountService, PlatformIdentity, platform_identity_from_request
from src.platform_rate_limit import check_platform_rate_limit


router = APIRouter()


def _billing_enabled() -> bool:
    return os.getenv("BILLING_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _billing_provider_name() -> str:
    return os.getenv("BILLING_PROVIDER", "disabled").strip().lower()


def _require_platform_user(request: Request) -> int:
    identity = platform_identity_from_request(request)
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})
    return int(identity.user_id)


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
    identity = platform_identity_from_request(request)
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Admin role required"})
    return identity


@router.post("/checkout")
async def create_checkout(request: Request, body: CheckoutRequest):
    require_csrf(request)
    user_id = _require_platform_user(request)
    limited = check_platform_rate_limit(request, "billing_checkout", user_id=user_id)
    if limited is not None:
        return limited
    if not _billing_enabled():
        return JSONResponse(
            status_code=400,
            content={"error": "billing_disabled", "message": "Billing is disabled in local V1"},
        )
    if _billing_provider_name() == "sandbox":
        try:
            session = SandboxPaymentProvider().create_checkout(user_id=user_id, plan=body.plan)
            BillingLifecycleService().record_checkout_created(
                user_id=user_id,
                provider_session_id=session.provider_session_id,
                checkout_url=session.checkout_url,
                plan=body.plan,
            )
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": "invalid_plan", "message": str(exc)})
        return {
            "checkout_url": session.checkout_url,
            "provider_session_id": session.provider_session_id,
            "provider": "sandbox",
            "plan": body.plan.strip().lower(),
            "status": "created",
            "mode": "local_sandbox",
        }
    return JSONResponse(
        status_code=501,
        content={"error": "billing_provider_not_configured", "message": "Payment provider is not configured"},
    )


@router.get("/account")
async def billing_account(request: Request):
    user_id = _require_platform_user(request)
    return BillingLifecycleService().get_user_billing_summary(
        user_id=user_id,
        billing_enabled=_billing_enabled(),
        provider=_billing_provider_name(),
    )


@router.get("/admin/events")
async def billing_admin_events(request: Request):
    _require_admin_identity(request)
    try:
        limit = int(request.query_params.get("limit", "100"))
    except ValueError:
        limit = 100
    return BillingLifecycleService().list_admin_billing_events(limit=limit)


@router.post("/webhook")
async def billing_webhook(request: Request):
    limited = check_platform_rate_limit(request, "billing_webhook")
    if limited is not None:
        return limited
    signature = request.headers.get("X-DSA-Billing-Signature", "")
    if not signature:
        return JSONResponse(status_code=400, content={"error": "invalid_signature"})
    if not _billing_enabled():
        return JSONResponse(status_code=400, content={"error": "billing_disabled"})
    if _billing_provider_name() == "sandbox":
        body = await request.body()
        try:
            payload = SandboxPaymentProvider().verify_webhook(body=body, signature=signature)
            result = BillingLifecycleService().process_verified_sandbox_event(payload)
            user = PlatformAccountService().get_user(int(result["user_id"])) if result.get("user_id") is not None else None
        except ValueError as exc:
            return JSONResponse(status_code=400, content={"error": str(exc)})
        response = {
            **result,
            "provider": "sandbox",
        }
        if user is not None:
            response["user"] = {
                "id": int(user.id),
                "email": user.email,
                "role": user.role,
                "plan": user.plan,
                "status": user.status,
            }
        return response
    return JSONResponse(status_code=501, content={"error": "billing_provider_not_configured"})

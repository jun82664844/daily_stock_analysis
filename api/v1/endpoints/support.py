# -*- coding: utf-8 -*-
"""Authenticated user and administrator support ticket endpoints."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, HTTPException, Query, Request, status

from api.v1.schemas.support import (
    SupportMessageCreateRequest,
    SupportStatus,
    SupportStatusUpdateRequest,
    SupportTicketCreateRequest,
    SupportTicketEnvelope,
    SupportTicketListResponse,
)
from src.auth import COOKIE_NAME, verify_session
from src.csrf import require_csrf
from src.platform_accounts import PlatformIdentity, platform_identity_from_request
from src.platform_audit import PlatformAuditLogger
from src.platform_rate_limit import check_platform_rate_limit
from src.services.platform_support_service import (
    PlatformSupportService,
    SupportInvalidStatus,
    SupportTicketClosed,
    SupportTicketNotFound,
)


router = APIRouter()


def _require_user(request: Request) -> PlatformIdentity:
    identity = platform_identity_from_request(request)
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail={"error": "unauthorized", "message": "Login required"})
    return identity


def _require_admin(request: Request) -> PlatformIdentity:
    admin_cookie = request.cookies.get(COOKIE_NAME)
    if admin_cookie and verify_session(admin_cookie):
        return PlatformIdentity(
            user_id=None,
            email="admin",
            role="admin",
            plan="enterprise",
            is_admin=True,
        )
    identity = _require_user(request)
    if not identity.is_admin:
        raise HTTPException(status_code=403, detail={"error": "forbidden", "message": "Admin role required"})
    return identity


def _audit(*, user_id: int | None, action: str, metadata: dict[str, Any]) -> None:
    try:
        PlatformAuditLogger().record(user_id=user_id, action=action, metadata=metadata)
    except Exception:
        pass


def _service_error(exc: Exception) -> HTTPException:
    if isinstance(exc, SupportTicketNotFound):
        return HTTPException(status_code=404, detail={"error": "ticket_not_found", "message": str(exc)})
    if isinstance(exc, SupportTicketClosed):
        return HTTPException(status_code=409, detail={"error": "ticket_closed", "message": str(exc)})
    if isinstance(exc, SupportInvalidStatus):
        return HTTPException(status_code=400, detail={"error": "invalid_status", "message": str(exc)})
    return HTTPException(status_code=400, detail={"error": "invalid_request", "message": str(exc)})


@router.post("/tickets", response_model=SupportTicketEnvelope, status_code=status.HTTP_201_CREATED)
async def create_support_ticket(request: Request, body: SupportTicketCreateRequest):
    require_csrf(request)
    identity = _require_user(request)
    user_id = int(identity.user_id)
    limited = check_platform_rate_limit(request, "support_ticket_create", user_id=user_id)
    if limited is not None:
        return limited
    ticket = PlatformSupportService().create_ticket(
        user_id=user_id,
        category=body.category,
        subject=body.subject,
        message=body.message,
    )
    _audit(
        user_id=user_id,
        action="support_ticket_created",
        metadata={"ticket_id": ticket["id"], "category": ticket["category"], "status": ticket["status"]},
    )
    return {"ticket": ticket}


@router.get("/tickets", response_model=SupportTicketListResponse)
async def list_support_tickets(request: Request, limit: int = Query(default=100, ge=1, le=200)):
    identity = _require_user(request)
    tickets = PlatformSupportService().list_user_tickets(user_id=int(identity.user_id), limit=limit)
    return {"tickets": tickets, "total": len(tickets)}


@router.get("/tickets/{ticket_id}", response_model=SupportTicketEnvelope)
async def get_support_ticket(request: Request, ticket_id: int):
    identity = _require_user(request)
    try:
        ticket = PlatformSupportService().get_user_ticket(user_id=int(identity.user_id), ticket_id=ticket_id)
    except (SupportTicketNotFound, SupportTicketClosed, SupportInvalidStatus) as exc:
        raise _service_error(exc) from exc
    return {"ticket": ticket}


@router.post("/tickets/{ticket_id}/messages", response_model=SupportTicketEnvelope)
async def add_support_message(request: Request, ticket_id: int, body: SupportMessageCreateRequest):
    require_csrf(request)
    identity = _require_user(request)
    user_id = int(identity.user_id)
    limited = check_platform_rate_limit(request, "support_ticket_message", user_id=user_id)
    if limited is not None:
        return limited
    try:
        ticket = PlatformSupportService().add_user_message(
            user_id=user_id,
            ticket_id=ticket_id,
            message=body.message,
        )
    except (SupportTicketNotFound, SupportTicketClosed, SupportInvalidStatus) as exc:
        raise _service_error(exc) from exc
    _audit(
        user_id=user_id,
        action="support_ticket_user_replied",
        metadata={"ticket_id": ticket["id"], "status": ticket["status"]},
    )
    return {"ticket": ticket}


@router.post("/tickets/{ticket_id}/close", response_model=SupportTicketEnvelope)
async def close_support_ticket(request: Request, ticket_id: int):
    require_csrf(request)
    identity = _require_user(request)
    user_id = int(identity.user_id)
    limited = check_platform_rate_limit(request, "support_ticket_status", user_id=user_id)
    if limited is not None:
        return limited
    try:
        ticket = PlatformSupportService().close_user_ticket(user_id=user_id, ticket_id=ticket_id)
    except (SupportTicketNotFound, SupportTicketClosed, SupportInvalidStatus) as exc:
        raise _service_error(exc) from exc
    _audit(
        user_id=user_id,
        action="support_ticket_user_closed",
        metadata={"ticket_id": ticket["id"], "status": ticket["status"]},
    )
    return {"ticket": ticket}


@router.get("/admin/tickets", response_model=SupportTicketListResponse)
async def list_admin_support_tickets(
    request: Request,
    status_filter: SupportStatus | None = Query(default=None, alias="status"),
    limit: int = Query(default=200, ge=1, le=500),
):
    _require_admin(request)
    try:
        tickets = PlatformSupportService().list_admin_tickets(status=status_filter, limit=limit)
    except SupportInvalidStatus as exc:
        raise _service_error(exc) from exc
    return {"tickets": tickets, "total": len(tickets)}


@router.get("/admin/tickets/{ticket_id}", response_model=SupportTicketEnvelope)
async def get_admin_support_ticket(request: Request, ticket_id: int):
    _require_admin(request)
    try:
        ticket = PlatformSupportService().get_admin_ticket(ticket_id=ticket_id)
    except (SupportTicketNotFound, SupportTicketClosed, SupportInvalidStatus) as exc:
        raise _service_error(exc) from exc
    return {"ticket": ticket}


@router.post("/admin/tickets/{ticket_id}/messages", response_model=SupportTicketEnvelope)
async def add_admin_support_message(request: Request, ticket_id: int, body: SupportMessageCreateRequest):
    require_csrf(request)
    identity = _require_admin(request)
    limited = check_platform_rate_limit(request, "support_admin_message", user_id=identity.user_id)
    if limited is not None:
        return limited
    try:
        ticket = PlatformSupportService().add_admin_message(ticket_id=ticket_id, message=body.message)
    except (SupportTicketNotFound, SupportTicketClosed, SupportInvalidStatus) as exc:
        raise _service_error(exc) from exc
    _audit(
        user_id=identity.user_id,
        action="support_ticket_admin_replied",
        metadata={"ticket_id": ticket["id"], "status": ticket["status"]},
    )
    return {"ticket": ticket}


@router.patch("/admin/tickets/{ticket_id}/status", response_model=SupportTicketEnvelope)
async def update_admin_support_status(request: Request, ticket_id: int, body: SupportStatusUpdateRequest):
    require_csrf(request)
    identity = _require_admin(request)
    limited = check_platform_rate_limit(request, "support_admin_status", user_id=identity.user_id)
    if limited is not None:
        return limited
    try:
        ticket = PlatformSupportService().update_admin_status(ticket_id=ticket_id, status=body.status)
    except (SupportTicketNotFound, SupportTicketClosed, SupportInvalidStatus) as exc:
        raise _service_error(exc) from exc
    _audit(
        user_id=identity.user_id,
        action="support_ticket_admin_status_updated",
        metadata={"ticket_id": ticket["id"], "status": ticket["status"]},
    )
    return {"ticket": ticket}

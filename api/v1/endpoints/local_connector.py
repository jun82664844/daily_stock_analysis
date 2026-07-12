from __future__ import annotations

import os

from fastapi import APIRouter, HTTPException, Query, Request
from fastapi.responses import JSONResponse

from api.v1.schemas.local_connector import (
    ConnectorClaimRequest,
    ConnectorHeartbeatRequest,
    ConnectorJobCompleteRequest,
)
from src.csrf import require_csrf
from src.platform_accounts import platform_identity_from_request
from src.services.user_local_connector_service import UserLocalConnectorService


router = APIRouter()


def _enabled() -> bool:
    return os.getenv("PLATFORM_USER_LOCAL_CONNECTOR_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _require_user(request: Request) -> int:
    identity = platform_identity_from_request(request)
    if identity is None or identity.user_id is None:
        raise HTTPException(status_code=401, detail={"error": "unauthorized"})
    return int(identity.user_id)


def _token(request: Request) -> str:
    value = request.headers.get("Authorization", "")
    if not value.startswith("Bearer "):
        raise HTTPException(status_code=401, detail={"error": "connector_unauthorized"})
    return value[7:].strip()


@router.post("/platform/local-connectors/pairing-code")
async def create_pairing_code(request: Request):
    require_csrf(request)
    if not _enabled():
        return JSONResponse(status_code=404, content={"error": "local_connector_disabled"})
    return UserLocalConnectorService().create_pairing(user_id=_require_user(request))


@router.get("/platform/local-connectors")
async def list_local_connectors(request: Request):
    if not _enabled():
        return {"connectors": [], "status": "disabled"}
    return {"connectors": UserLocalConnectorService().list_connectors(_require_user(request)), "status": "enabled"}


@router.delete("/platform/local-connectors/{connector_id}")
async def revoke_local_connector(connector_id: int, request: Request):
    require_csrf(request)
    if not UserLocalConnectorService().revoke(_require_user(request), connector_id):
        return JSONResponse(status_code=404, content={"error": "connector_not_found"})
    return {"revoked": True, "connector_id": connector_id}


@router.post("/local-connector/claim")
async def claim_local_connector(body: ConnectorClaimRequest):
    if not _enabled():
        return JSONResponse(status_code=404, content={"error": "local_connector_disabled"})
    try:
        return UserLocalConnectorService().claim_pairing(body.pairing_code, device_name=body.device_name)
    except ValueError as exc:
        return JSONResponse(status_code=400, content={"error": str(exc)})


@router.post("/local-connector/heartbeat")
async def local_connector_heartbeat(request: Request, body: ConnectorHeartbeatRequest):
    try:
        return UserLocalConnectorService().heartbeat(_token(request), body.models)
    except ValueError:
        return JSONResponse(status_code=401, content={"error": "connector_unauthorized"})


@router.get("/local-connector/jobs/next")
def next_local_connector_job(request: Request, wait_seconds: int = Query(25, ge=0, le=25)):
    try:
        return UserLocalConnectorService().next_job(_token(request), wait_seconds=wait_seconds)
    except ValueError:
        return JSONResponse(status_code=401, content={"error": "connector_unauthorized"})


@router.post("/local-connector/jobs/{job_id}/complete")
async def complete_local_connector_job(job_id: str, request: Request, body: ConnectorJobCompleteRequest):
    try:
        return UserLocalConnectorService().complete_job(_token(request), job_id, body.result)
    except ValueError as exc:
        error = str(exc)
        status = 404 if error == "job_not_found" else 400 if error == "invalid_job_result" else 401
        return JSONResponse(status_code=status, content={"error": str(exc)})

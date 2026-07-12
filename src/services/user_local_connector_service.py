# -*- coding: utf-8 -*-
"""Pairing, token isolation and encrypted jobs for user-owned Ollama connectors."""

from __future__ import annotations

import hashlib
import json
import os
import secrets
import threading
import time
import uuid
from datetime import datetime, timedelta
from typing import Any, Dict, Optional

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.platform_accounts import _load_fernet
from src.storage import (
    DatabaseManager,
    PlatformLocalConnector,
    PlatformLocalModelJob,
    utc_naive_now,
)


class UserLocalConnectorService:
    _pairings: Dict[str, Dict[str, Any]] = {}
    _pairing_lock = threading.RLock()

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()

    @staticmethod
    def _token_hash(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def create_pairing(self, *, user_id: int) -> Dict[str, Any]:
        ttl = max(60, int(os.getenv("PLATFORM_LOCAL_CONNECTOR_PAIRING_TTL_SECONDS", "300")))
        code = f"{secrets.randbelow(1_000_000):06d}"
        digest = self._token_hash(code)
        expires_at = utc_naive_now() + timedelta(seconds=ttl)
        with self._pairing_lock:
            self._pairings[digest] = {"user_id": int(user_id), "expires_at": expires_at, "used": False}
        return {"code": code, "expires_at": f"{expires_at.isoformat()}Z", "ttl_seconds": ttl}

    def claim_pairing(self, code: str, *, device_name: str) -> Dict[str, Any]:
        digest = self._token_hash((code or "").strip())
        with self._pairing_lock:
            pairing = self._pairings.get(digest)
            if pairing is None or pairing["expires_at"] <= utc_naive_now():
                raise ValueError("pairing_code_invalid")
            if pairing["used"]:
                raise ValueError("pairing_code_used")
            pairing["used"] = True
            user_id = int(pairing["user_id"])
        token = secrets.token_urlsafe(48)
        now = utc_naive_now()
        with self.db.session_scope() as session:
            row = PlatformLocalConnector(
                user_id=user_id,
                device_name=(device_name or "DSA Local Connector").strip()[:128],
                device_token_hash=self._token_hash(token),
                models_json="[]",
                status="online",
                last_seen_at=now,
                created_at=now,
            )
            session.add(row)
            session.flush()
            connector_id = int(row.id)
        return {"connector_id": connector_id, "device_token": token, "status": "online"}

    def _connector_for_token(self, session: Session, token: str) -> PlatformLocalConnector:
        row = session.execute(
            select(PlatformLocalConnector).where(
                PlatformLocalConnector.device_token_hash == self._token_hash(token or "")
            )
        ).scalars().first()
        if row is None or row.revoked_at is not None:
            raise ValueError("connector_unauthorized")
        return row

    def heartbeat(self, token: str, models: list[str]) -> Dict[str, Any]:
        safe_models = []
        seen = set()
        for item in models:
            model = str(item).strip()[:160]
            if not model or model in seen:
                continue
            seen.add(model)
            safe_models.append(model)
            if len(safe_models) >= 50:
                break
        with self.db.session_scope() as session:
            row = self._connector_for_token(session, token)
            row.models_json = json.dumps(safe_models, ensure_ascii=False)
            row.status = "online"
            row.last_seen_at = utc_naive_now()
            return {"connector_id": int(row.id), "models": safe_models, "status": "online"}

    @staticmethod
    def _online_cutoff() -> datetime:
        ttl = max(30, int(os.getenv("PLATFORM_LOCAL_CONNECTOR_ONLINE_TTL_SECONDS", "90")))
        return utc_naive_now() - timedelta(seconds=ttl)

    def list_online_connectors(self, user_id: int) -> list[Dict[str, Any]]:
        cutoff = self._online_cutoff()
        with self.db.get_session() as session:
            rows = session.execute(
                select(PlatformLocalConnector).where(
                    PlatformLocalConnector.user_id == int(user_id),
                    PlatformLocalConnector.revoked_at.is_(None),
                    PlatformLocalConnector.status == "online",
                    PlatformLocalConnector.last_seen_at.is_not(None),
                    PlatformLocalConnector.last_seen_at >= cutoff,
                ).order_by(PlatformLocalConnector.id)
            ).scalars().all()
            return [
                {
                    "id": int(row.id),
                    "device_name": row.device_name,
                    "models": json.loads(row.models_json or "[]"),
                    "status": "online",
                    "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
                }
                for row in rows
            ]

    def create_job(
        self,
        *,
        user_id: int,
        connector_id: int,
        model_name: str,
        request_payload: Dict[str, Any],
        expires_at: Optional[datetime] = None,
    ) -> Dict[str, Any]:
        now = utc_naive_now()
        ttl = max(30, int(os.getenv("PLATFORM_LOCAL_JOB_TTL_SECONDS", "120")))
        job_id = uuid.uuid4().hex
        ciphertext = _load_fernet().encrypt(
            json.dumps(request_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).decode("ascii")
        with self.db.session_scope() as session:
            connector = session.get(PlatformLocalConnector, int(connector_id))
            if connector is None or int(connector.user_id) != int(user_id) or connector.revoked_at is not None:
                raise ValueError("connector_not_found")
            session.add(
                PlatformLocalModelJob(
                    id=job_id,
                    user_id=int(user_id),
                    connector_id=int(connector_id),
                    model_name=(model_name or "").strip()[:160],
                    request_ciphertext=ciphertext,
                    status="queued",
                    expires_at=expires_at or (now + timedelta(seconds=ttl)),
                    created_at=now,
                    updated_at=now,
                )
            )
        return {"job_id": job_id, "status": "queued"}

    def next_job(self, token: str, *, wait_seconds: int = 25) -> Optional[Dict[str, Any]]:
        deadline = time.monotonic() + max(0, min(int(wait_seconds), 25))
        while True:
            with self.db.session_scope() as session:
                connector = self._connector_for_token(session, token)
                now = utc_naive_now()
                row = session.execute(
                    select(PlatformLocalModelJob).where(
                        PlatformLocalModelJob.connector_id == int(connector.id),
                        PlatformLocalModelJob.user_id == int(connector.user_id),
                        PlatformLocalModelJob.status == "queued",
                        PlatformLocalModelJob.expires_at > now,
                    ).order_by(PlatformLocalModelJob.created_at, PlatformLocalModelJob.id)
                ).scalars().first()
                if row is not None:
                    row.status = "running"
                    row.updated_at = now
                    payload = json.loads(_load_fernet().decrypt(row.request_ciphertext.encode("ascii")).decode("utf-8"))
                    return {"job_id": row.id, "model": row.model_name, "request": payload, "expires_at": row.expires_at.isoformat()}
            if time.monotonic() >= deadline:
                return None
            time.sleep(0.2)

    def complete_job(self, token: str, job_id: str, response_payload: Dict[str, Any]) -> Dict[str, Any]:
        if not isinstance(response_payload, dict) or not set(response_payload).issubset(
            {"text", "diagnostics", "error"}
        ):
            raise ValueError("invalid_job_result")
        text = response_payload.get("text")
        error = response_payload.get("error")
        diagnostics = response_payload.get("diagnostics") or {}
        if text is not None and not isinstance(text, str):
            raise ValueError("invalid_job_result")
        if error is not None and not isinstance(error, str):
            raise ValueError("invalid_job_result")
        if not isinstance(diagnostics, dict):
            raise ValueError("invalid_job_result")
        allowed_diagnostics = {
            key: value
            for key, value in diagnostics.items()
            if key in {"done_reason", "total_duration_ms", "eval_count", "eval_duration_ms"}
            and isinstance(value, (str, int, float, bool, type(None)))
        }
        safe_payload = {
            "text": (text or "")[:100_000],
            "diagnostics": allowed_diagnostics,
        }
        if error:
            safe_payload["error"] = error[:160]
        with self.db.session_scope() as session:
            connector = self._connector_for_token(session, token)
            row = session.execute(
                select(PlatformLocalModelJob).where(
                    PlatformLocalModelJob.id == str(job_id),
                    PlatformLocalModelJob.connector_id == int(connector.id),
                    PlatformLocalModelJob.user_id == int(connector.user_id),
                )
            ).scalars().first()
            if row is None:
                raise ValueError("job_not_found")
            row.response_ciphertext = _load_fernet().encrypt(
                json.dumps(safe_payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
            ).decode("ascii")
            row.status = "failed" if error else "completed"
            row.updated_at = utc_naive_now()
            return {"job_id": row.id, "status": row.status}

    def wait_for_result(
        self,
        *,
        user_id: int,
        job_id: str,
        timeout_seconds: float,
    ) -> Dict[str, Any]:
        deadline = time.monotonic() + max(0.0, min(float(timeout_seconds), 180.0))
        while True:
            with self.db.get_session() as session:
                row = session.execute(
                    select(PlatformLocalModelJob).where(
                        PlatformLocalModelJob.id == str(job_id),
                        PlatformLocalModelJob.user_id == int(user_id),
                    )
                ).scalars().first()
                if row is None:
                    raise ValueError("job_not_found")
                if row.expires_at <= utc_naive_now():
                    raise TimeoutError("user_local_model_timeout")
                if row.status in {"completed", "failed"}:
                    payload = json.loads(
                        _load_fernet().decrypt(row.response_ciphertext.encode("ascii")).decode("utf-8")
                    )
                    if row.status == "failed":
                        raise RuntimeError(str(payload.get("error") or "user_local_model_failed"))
                    return payload
            if time.monotonic() >= deadline:
                raise TimeoutError("user_local_model_timeout")
            time.sleep(0.1)

    def run_analysis(
        self,
        *,
        user_id: int,
        connector_id: int,
        model_name: str,
        stock_code: str,
        report_language: str,
        analysis_depth: str,
        snapshot: Dict[str, Any],
    ) -> Dict[str, Any]:
        connectors = {item["id"]: item for item in self.list_online_connectors(user_id)}
        connector = connectors.get(int(connector_id))
        if connector is None:
            raise ValueError("user_local_connector_offline")
        if model_name not in connector["models"]:
            raise ValueError("user_local_model_not_available")
        language_instruction = "Reply in English." if report_language == "en" else "请用中文回答。"
        compact_snapshot = {
            key: snapshot.get(key)
            for key in (
                "stock_code",
                "stock_name",
                "market",
                "quote",
                "indicators",
                "profile",
                "freshness",
                "warnings",
                "source_status",
            )
            if snapshot.get(key) is not None
        }
        snapshot_json = json.dumps(
            compact_snapshot,
            ensure_ascii=False,
            default=str,
            separators=(",", ":"),
        )[:12_000]
        prompt = (
            "You are a read-only financial information summarizer. Use only the supplied market snapshot. "
            "Describe price, trend, volume, data freshness, company facts, and uncertainty. "
            "Be concise: at most eight short bullet points and no chain-of-thought. "
            "Do not provide buy/sell/hold instructions, position sizing, target prices, stop-loss/take-profit, "
            f"return forecasts, or personalized investment advice. {language_instruction}\n"
            f"Symbol: {stock_code}\nAnalysis depth: {analysis_depth}\nSnapshot JSON: {snapshot_json}"
        )
        job = self.create_job(
            user_id=user_id,
            connector_id=connector_id,
            model_name=model_name,
            request_payload={
                "task": "stock_information_summary",
                "prompt": prompt,
                "response_format": "plain_text",
            },
        )
        timeout = max(5.0, float(os.getenv("PLATFORM_LOCAL_JOB_WAIT_SECONDS", "120")))
        result = self.wait_for_result(
            user_id=user_id,
            job_id=job["job_id"],
            timeout_seconds=timeout,
        )
        return {
            **result,
            "connector_id": int(connector_id),
            "model_name": model_name,
            "job_id": job["job_id"],
        }

    def list_connectors(self, user_id: int) -> list[Dict[str, Any]]:
        with self.db.get_session() as session:
            rows = session.execute(
                select(PlatformLocalConnector).where(PlatformLocalConnector.user_id == int(user_id))
            ).scalars().all()
            return [{
                "id": int(row.id),
                "device_name": row.device_name,
                "models": json.loads(row.models_json or "[]"),
                "status": row.status if row.revoked_at is None else "revoked",
                "last_seen_at": row.last_seen_at.isoformat() if row.last_seen_at else None,
            } for row in rows]

    def revoke(self, user_id: int, connector_id: int) -> bool:
        with self.db.session_scope() as session:
            row = session.execute(
                select(PlatformLocalConnector).where(
                    PlatformLocalConnector.id == int(connector_id),
                    PlatformLocalConnector.user_id == int(user_id),
                )
            ).scalars().first()
            if row is None:
                return False
            row.revoked_at = utc_naive_now()
            row.status = "revoked"
            return True

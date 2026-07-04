# -*- coding: utf-8 -*-
"""Provider-neutral billing boundary for V2 launch preparation."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass


@dataclass(frozen=True)
class CheckoutSession:
    checkout_url: str
    provider_session_id: str


class PaymentProvider:
    def create_checkout(self, *, user_id: int, plan: str) -> CheckoutSession:
        raise NotImplementedError

    def verify_webhook(self, *, body: bytes, signature: str) -> dict:
        raise NotImplementedError


class SandboxPaymentProvider(PaymentProvider):
    """Local-only billing provider used for signed sandbox upgrade tests."""

    ALLOWED_PLANS = {"pro", "premium", "enterprise"}
    ALLOWED_SUBSCRIPTION_PLANS = {"free", "pro", "premium", "enterprise"}
    SUPPORTED_EVENTS = {
        "checkout.created",
        "checkout.completed",
        "checkout.cancelled",
        "checkout.expired",
        "payment.failed",
        "subscription.updated",
    }

    def __init__(self, *, secret: str | None = None) -> None:
        self.secret = (secret or os.getenv("BILLING_SANDBOX_SECRET") or "local-sandbox-secret").encode("utf-8")

    def create_checkout(self, *, user_id: int, plan: str) -> CheckoutSession:
        normalized_plan = (plan or "").strip().lower()
        if normalized_plan not in self.ALLOWED_PLANS:
            raise ValueError(f"unsupported sandbox plan: {plan}")
        nonce = secrets.token_urlsafe(8).replace("_", "")
        session_id = f"sandbox_{int(user_id)}_{normalized_plan}_{nonce}"
        return CheckoutSession(
            checkout_url=f"/sandbox/checkout/{session_id}",
            provider_session_id=session_id,
        )

    def verify_webhook(self, *, body: bytes, signature: str) -> dict:
        expected = hmac.new(self.secret, body, hashlib.sha256).hexdigest()
        if not signature or not hmac.compare_digest(signature, expected):
            raise ValueError("invalid_signature")
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid_payload") from exc

        event_type = str(payload.get("event") or "").strip().lower()
        if event_type not in self.SUPPORTED_EVENTS:
            raise ValueError("unsupported_event")

        if event_type == "subscription.updated":
            try:
                user_id = int(payload.get("user_id"))
            except (TypeError, ValueError) as exc:
                raise ValueError("invalid_user_id") from exc
            plan = str(payload.get("plan") or "").strip().lower()
            if plan not in self.ALLOWED_SUBSCRIPTION_PLANS:
                raise ValueError("unsupported_plan")
            return {
                "event": event_type,
                "provider_event_id": str(payload.get("provider_event_id") or "").strip(),
                "provider_session_id": str(payload.get("provider_session_id") or "").strip(),
                "provider_subscription_id": str(payload.get("provider_subscription_id") or "").strip(),
                "user_id": user_id,
                "plan": plan,
                "subscription_status": str(
                    payload.get("subscription_status") or payload.get("status") or "active"
                ).strip().lower(),
            }

        session_id = str(payload.get("provider_session_id") or "")
        parts = session_id.split("_", 3)
        if len(parts) != 4 or parts[0] != "sandbox":
            raise ValueError("invalid_session")
        try:
            user_id = int(parts[1])
        except ValueError as exc:
            raise ValueError("invalid_session") from exc
        plan = parts[2]
        if plan not in self.ALLOWED_PLANS:
            raise ValueError("unsupported_plan")
        return {
            "event": event_type,
            "provider_event_id": str(payload.get("provider_event_id") or "").strip(),
            "provider_session_id": session_id,
            "user_id": user_id,
            "plan": plan,
        }

# -*- coding: utf-8 -*-
"""Provider-neutral billing boundary for V2 launch preparation."""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import secrets
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CheckoutSession:
    checkout_url: str
    provider_session_id: str


class PaymentProvider:
    def create_checkout(self, *, user_id: int, plan: str) -> CheckoutSession:
        raise NotImplementedError

    def verify_webhook(self, *, body: bytes, signature: str) -> dict:
        raise NotImplementedError


REAL_PROVIDER_REQUIREMENTS = {
    "stripe": (
        "BILLING_STRIPE_SECRET_KEY",
        "BILLING_STRIPE_WEBHOOK_SECRET",
        "BILLING_STRIPE_PRICE_PRO",
    )
}


def _env_enabled(name: str, default: str = "false") -> bool:
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _env_provider() -> str:
    return os.getenv("BILLING_PROVIDER", "disabled").strip().lower() or "disabled"


def get_payment_provider_status() -> dict[str, Any]:
    """Return sanitized provider readiness without exposing secret values."""

    billing_enabled = _env_enabled("BILLING_ENABLED")
    provider = _env_provider()
    if not billing_enabled:
        return {
            "billing_enabled": False,
            "provider": provider,
            "mode": "disabled",
            "configuration_ready": False,
            "adapter_implemented": False,
            "ready_for_checkout": False,
            "required_config": [],
            "missing_config": [],
            "copy": "Billing is disabled; no real payment processing is available.",
        }

    if provider == "sandbox":
        return {
            "billing_enabled": True,
            "provider": "sandbox",
            "mode": "local_sandbox",
            "configuration_ready": True,
            "adapter_implemented": True,
            "ready_for_checkout": True,
            "required_config": ["BILLING_SANDBOX_SECRET"],
            "missing_config": [],
            "copy": "Local sandbox billing only; not real payment processing.",
        }

    required = list(REAL_PROVIDER_REQUIREMENTS.get(provider, ()))
    if not required:
        return {
            "billing_enabled": True,
            "provider": provider,
            "mode": "unsupported_provider",
            "configuration_ready": False,
            "adapter_implemented": False,
            "ready_for_checkout": False,
            "required_config": [],
            "missing_config": [],
            "copy": "Payment provider is not supported by the local adapter boundary.",
        }

    missing = [key for key in required if not os.getenv(key, "").strip()]
    configuration_ready = not missing
    return {
        "billing_enabled": True,
        "provider": provider,
        "mode": "real_provider_configured_not_implemented" if configuration_ready else "real_provider_missing_config",
        "configuration_ready": configuration_ready,
        "adapter_implemented": False,
        "ready_for_checkout": False,
        "required_config": required,
        "missing_config": missing,
        "copy": (
            "Real payment provider configuration is recognized, but the live adapter is not implemented "
            "and must not process real payments in local mode."
        ),
    }


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

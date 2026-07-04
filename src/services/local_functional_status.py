# -*- coding: utf-8 -*-
"""Sanitized local-only functional status for the admin console."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from src.services.market_source_ops import build_market_source_ops_snapshot


TRUE_VALUES = {"1", "true", "yes", "on"}


def build_local_functional_status() -> dict[str, Any]:
    """Build a no-AI, secret-free status payload for local operators."""

    billing_enabled = _env_bool("BILLING_ENABLED", False)
    billing_provider = _env_str("BILLING_PROVIDER", "disabled" if not billing_enabled else "sandbox")
    market = build_market_source_ops_snapshot()
    return {
        "mode": "local_only",
        "ai_used": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "service": {
            "webui": "ok",
            "host": _env_str("WEBUI_HOST", _env_str("API_HOST", "127.0.0.1")),
            "port": _env_int("WEBUI_PORT", _env_int("API_PORT", 8000)),
        },
        "auth": {
            "platform_user_auth_enabled": _env_bool("PLATFORM_USER_AUTH_ENABLED", True),
            "admin_auth_enabled": _env_bool("ADMIN_AUTH_ENABLED", False),
            "csrf_enabled": _env_bool("PLATFORM_CSRF_ENABLED", True),
        },
        "billing": {
            "enabled": billing_enabled,
            "provider": billing_provider if billing_enabled else "disabled",
            "mode": "local_sandbox" if billing_enabled and billing_provider == "sandbox" else "local_only",
        },
        "ai": {
            "default_model": _env_str("LITELLM_MODEL", ""),
            "agent_model": _env_str("AGENT_LITELLM_MODEL", ""),
            "local_model_enabled": _env_bool("LOCAL_LLM_ENABLED", False),
            "local_model_max_concurrent": _env_int("LOCAL_LLM_MAX_CONCURRENT", 0),
            "byok_supported": True,
            "public_search_enabled": _env_bool("SEARXNG_PUBLIC_INSTANCES_ENABLED", False),
        },
        "market": {
            "summary": dict(market.get("summary") or {}),
            "cache": dict(market.get("cache") or {}),
            "lanes": list(market.get("lanes") or []),
        },
        "safety": {
            "no_ai_status": market.get("ai_used") is False,
            "secrets_redacted": True,
            "real_payment_enabled": False,
            "local_only": True,
        },
    }


def _env_str(key: str, default: str) -> str:
    return str(os.getenv(key, default) or default).strip()


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    return value.strip().lower() in TRUE_VALUES


def _env_int(key: str, default: int) -> int:
    value = os.getenv(key)
    if value is None:
        return default
    try:
        return int(str(value).strip())
    except (TypeError, ValueError):
        return default

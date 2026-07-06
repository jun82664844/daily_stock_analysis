"""Production-readiness preflight for the platform admin console.

The preflight is intentionally conservative: missing human approvals or real
provider evidence blocks launch instead of guessing that a public rollout is
safe. It never returns secret values or secret environment variable names.
"""

from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any

from src.billing.payment_provider import get_payment_provider_status


TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off", ""}


def build_production_readiness_status() -> dict[str, Any]:
    """Build a sanitized GO/NO-GO payload for production launch review."""

    checks = [
        _check_bool(
            "admin_auth_enabled",
            "auth",
            "Admin authentication enabled",
            _env_bool("ADMIN_AUTH_ENABLED", False),
            "Admin routes must require an authenticated admin session.",
        ),
        _check_bool(
            "platform_auth_enabled",
            "auth",
            "Platform user authentication enabled",
            _env_bool("PLATFORM_USER_AUTH_ENABLED", False),
            "Public user accounts must be protected before paid usage.",
        ),
        _check_bool(
            "csrf_enabled",
            "auth",
            "CSRF protection enabled",
            _env_bool("PLATFORM_CSRF_ENABLED", True),
            "Cookie-backed unsafe requests require CSRF protection.",
        ),
        _check_false(
            "cors_locked_down",
            "security",
            "CORS wildcard disabled",
            _env_bool("CORS_ALLOW_ALL", False),
            "Production must use an explicit origin allowlist.",
        ),
        _check_false(
            "debug_disabled",
            "security",
            "Debug mode disabled",
            _env_bool("DEBUG", False),
            "Debug output must not be exposed to public users.",
        ),
        _check_bool(
            "managed_secret_source",
            "security",
            "Managed secret source configured",
            _secret_source_is_managed(),
            "Production secrets must live outside committed files.",
        ),
        _check_false(
            "public_search_disabled",
            "security",
            "Public search auto-discovery disabled",
            _env_bool("SEARXNG_PUBLIC_INSTANCES_ENABLED", False),
            "Public SearXNG instances are unreliable and may leak or throttle traffic.",
        ),
        _billing_check(),
        _approval_check(
            "domain_not_approved",
            "deployment",
            "Production domain approved",
            "DSA_PRODUCTION_DOMAIN_APPROVED",
            "A real domain and routing plan must be approved before launch.",
        ),
        _approval_check(
            "https_not_approved",
            "deployment",
            "HTTPS/TLS approved",
            "DSA_PRODUCTION_HTTPS_APPROVED",
            "Production traffic must use HTTPS with managed certificates.",
        ),
        _approval_check(
            "waf_not_approved",
            "deployment",
            "WAF/CDN policy approved",
            "DSA_PRODUCTION_WAF_APPROVED",
            "Public traffic needs rate, bot, and abuse controls at the edge.",
        ),
        _approval_check(
            "market_data_license_not_approved",
            "data_sources",
            "Market data commercial license approved",
            "DSA_MARKET_DATA_LICENSE_APPROVED",
            "Free local data sources are not automatically approved for commercial service.",
        ),
        _approval_check(
            "legal_terms_not_approved",
            "legal",
            "Legal terms approved",
            "DSA_LEGAL_TERMS_APPROVED",
            "Terms must be reviewed by humans before public launch.",
        ),
        _check_bool(
            "not_investment_advice_visible",
            "legal",
            "Not-investment-advice boundary enabled",
            _env_bool("DSA_ANALYSIS_NOT_INVESTMENT_ADVICE", True),
            "Analysis output must stay informational and not be presented as investment advice.",
        ),
        _approval_check(
            "privacy_policy_not_approved",
            "privacy",
            "Privacy policy approved",
            "DSA_PRIVACY_POLICY_APPROVED",
            "The product stores account, usage, API-key metadata, history, and billing records.",
        ),
        _approval_check(
            "monitoring_not_approved",
            "observability",
            "Monitoring and alerting approved",
            "DSA_MONITORING_APPROVED",
            "Production needs API, billing, data-source, and AI-cost monitoring.",
        ),
        _approval_check(
            "backup_restore_not_approved",
            "backup",
            "Backup and restore drill approved",
            "DSA_BACKUP_RESTORE_DRILL_APPROVED",
            "A staging restore drill is required before public launch.",
        ),
    ]
    blocking_checks = [check for check in checks if check["status"] == "blocked"]
    manual_actions = [
        {
            "id": check["id"],
            "category": check["category"],
            "action": check["message"],
        }
        for check in blocking_checks
    ]
    production_ready = not blocking_checks
    return {
        "mode": "production_preflight",
        "ai_used": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "launch_decision": "ready" if production_ready else "blocked",
        "production_ready": production_ready,
        "analysis_boundary": "not_investment_advice",
        "checks": checks,
        "blocking_checks": blocking_checks,
        "manual_actions": manual_actions,
        "summary": {
            "total": len(checks),
            "passed": len([check for check in checks if check["status"] == "passed"]),
            "blocked": len(blocking_checks),
            "manual_actions": len(manual_actions),
        },
    }


def _check_bool(check_id: str, category: str, title: str, value: bool, message: str) -> dict[str, Any]:
    return _check(
        check_id=check_id,
        category=category,
        title=title,
        passed=value,
        blocked_message=message,
    )


def _check_false(check_id: str, category: str, title: str, value: bool, message: str) -> dict[str, Any]:
    return _check(
        check_id=check_id,
        category=category,
        title=title,
        passed=not value,
        blocked_message=message,
    )


def _approval_check(blocked_id: str, category: str, title: str, env_key: str, message: str) -> dict[str, Any]:
    return _check(
        check_id=blocked_id,
        category=category,
        title=title,
        passed=_env_bool(env_key, False),
        blocked_message=message,
    )


def _billing_check() -> dict[str, Any]:
    provider_status = get_payment_provider_status()
    billing_enabled = bool(provider_status["billing_enabled"])
    provider = str(provider_status["provider"])
    real_provider = billing_enabled and provider not in {"", "disabled", "sandbox"}
    approved = _env_bool("DSA_REAL_PAYMENT_APPROVED", False)
    webhook_approved = _env_bool("DSA_PAYMENT_WEBHOOK_APPROVED", False)
    passed = (
        real_provider
        and bool(provider_status["configuration_ready"])
        and bool(provider_status["adapter_implemented"])
        and approved
        and webhook_approved
    )
    if passed:
        message = "Real payment provider and signed webhook path are approved."
    elif not billing_enabled:
        message = "No real payment provider is enabled; paid public launch remains blocked."
    elif provider == "sandbox":
        message = "Sandbox billing is test-only and cannot be used as production payment."
    elif not provider_status["configuration_ready"]:
        message = "Real payment provider configuration is incomplete; no payment launch is allowed."
    elif not provider_status["adapter_implemented"]:
        message = "Real payment provider configuration is present, but the live adapter is not implemented."
    else:
        message = "Real payment provider needs merchant, webhook, reconciliation, refund, and invoice approval."
    return {
        "id": "real_payment_configured" if passed else (
            "real_payment_disabled" if not billing_enabled else "real_payment_provider_not_ready"
        ),
        "category": "billing",
        "title": "Real payment provider approved",
        "status": "passed" if passed else "blocked",
        "severity": "info" if passed else "critical",
        "message": message,
        "evidence": {
            "provider_mode": "real_provider" if real_provider else ("sandbox" if provider == "sandbox" else "disabled"),
            "provider": provider,
            "configuration_ready": bool(provider_status["configuration_ready"]),
            "adapter_implemented": bool(provider_status["adapter_implemented"]),
            "missing_config": provider_status["missing_config"],
            "webhook_approved": webhook_approved,
        },
    }


def _check(
    *,
    check_id: str,
    category: str,
    title: str,
    passed: bool,
    blocked_message: str,
) -> dict[str, Any]:
    return {
        "id": check_id,
        "category": category,
        "title": title,
        "status": "passed" if passed else "blocked",
        "severity": "info" if passed else "critical",
        "message": "Ready for launch review." if passed else blocked_message,
        "evidence": {
            "configured": passed,
        },
    }


def _secret_source_is_managed() -> bool:
    value = _env_str("DSA_SECRET_SOURCE", "")
    return value in {"managed-secret-store-or-protected-env", "managed_secret_store", "protected_env"}


def _env_str(key: str, default: str) -> str:
    return str(os.getenv(key, default) or default).strip()


def _env_bool(key: str, default: bool) -> bool:
    value = os.getenv(key)
    if value is None:
        return default
    normalized = str(value).strip().lower()
    if normalized in TRUE_VALUES:
        return True
    if normalized in FALSE_VALUES:
        return False
    return default

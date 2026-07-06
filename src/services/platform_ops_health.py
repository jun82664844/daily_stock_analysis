from __future__ import annotations

import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from src.billing.payment_provider import get_payment_provider_status


REPO_ROOT = Path(__file__).resolve().parents[2]


def _env_bool(name: str, default: bool = False) -> bool:
    fallback = "true" if default else "false"
    return os.getenv(name, fallback).strip().lower() in {"1", "true", "yes", "on"}


def _check(
    check_id: str,
    category: str,
    title: str,
    *,
    ok: bool,
    message: str,
    evidence: dict[str, Any] | None = None,
    severity: str = "warning",
) -> dict[str, Any]:
    return {
        "id": check_id,
        "category": category,
        "title": title,
        "status": "ok" if ok else "degraded",
        "severity": "info" if ok else severity,
        "message": message,
        "evidence": evidence or {},
    }


def _database_check() -> list[dict[str, Any]]:
    raw_path = os.getenv("DATABASE_PATH", "").strip()
    configured = bool(raw_path)
    exists = Path(raw_path).exists() if configured else False
    reachable = False
    quick_check = "not_run"
    if exists:
        try:
            with sqlite3.connect(f"file:{Path(raw_path).as_posix()}?mode=ro", uri=True) as conn:
                conn.execute("SELECT 1").fetchone()
                quick_check = str(conn.execute("PRAGMA quick_check").fetchone()[0])
                reachable = True
        except sqlite3.Error as exc:
            quick_check = type(exc).__name__
    return [
        _check(
            "database_configured",
            "database",
            "Database path configured",
            ok=configured,
            message="Database path is configured." if configured else "DATABASE_PATH is not configured.",
            evidence={"configured": configured},
        ),
        _check(
            "database_reachable",
            "database",
            "Database reachable",
            ok=reachable and quick_check == "ok",
            message="Database is reachable and quick_check is ok." if reachable and quick_check == "ok" else "Database is not reachable or quick_check failed.",
            evidence={"exists": exists, "reachable": reachable, "quick_check": quick_check},
            severity="critical",
        ),
    ]


def _config_checks() -> list[dict[str, Any]]:
    return [
        _check(
            "debug_disabled",
            "security",
            "Debug disabled",
            ok=not _env_bool("DEBUG", False),
            message="DEBUG is disabled." if not _env_bool("DEBUG", False) else "DEBUG is enabled.",
        ),
        _check(
            "cors_wildcard_disabled",
            "security",
            "CORS wildcard disabled",
            ok=not _env_bool("CORS_ALLOW_ALL", False),
            message="CORS wildcard is disabled." if not _env_bool("CORS_ALLOW_ALL", False) else "CORS wildcard is enabled.",
        ),
        _check(
            "public_search_disabled",
            "security",
            "Public SearXNG auto-discovery disabled",
            ok=not _env_bool("SEARXNG_PUBLIC_INSTANCES_ENABLED", False),
            message=(
                "Public SearXNG auto-discovery is disabled."
                if not _env_bool("SEARXNG_PUBLIC_INSTANCES_ENABLED", False)
                else "Public SearXNG auto-discovery is enabled."
            ),
        ),
        _check(
            "auth_csrf_enabled",
            "security",
            "Auth and CSRF enabled",
            ok=(
                _env_bool("ADMIN_AUTH_ENABLED", True)
                and _env_bool("PLATFORM_USER_AUTH_ENABLED", True)
                and _env_bool("PLATFORM_CSRF_ENABLED", True)
            ),
            message="Admin auth, platform auth, and CSRF are enabled.",
            severity="critical",
        ),
    ]


def _file_checks() -> list[dict[str, Any]]:
    backup_runner = REPO_ROOT / "scripts" / "run_platform_backup_restore_dry_run.py"
    backup_verifier = REPO_ROOT / "scripts" / "verify_platform_backup_restore_drill_v51.py"
    readiness_verifier = REPO_ROOT / "scripts" / "verify_platform_production_readiness_v48.py"
    return [
        _check(
            "backup_runner_available",
            "backup",
            "Backup restore dry-run runner available",
            ok=backup_runner.exists() and backup_verifier.exists(),
            message="Backup restore dry-run runner and verifier are available.",
            evidence={"runner_exists": backup_runner.exists(), "verifier_exists": backup_verifier.exists()},
            severity="critical",
        ),
        _check(
            "production_readiness_verifier_available",
            "observability",
            "Production readiness verifier available",
            ok=readiness_verifier.exists(),
            message="Production readiness verifier is available." if readiness_verifier.exists() else "Production readiness verifier is missing.",
            evidence={"verifier_exists": readiness_verifier.exists()},
        ),
    ]


def _billing_check() -> dict[str, Any]:
    status = get_payment_provider_status()
    safe_status = {
        "billing_enabled": bool(status.get("billing_enabled")),
        "provider": status.get("provider"),
        "mode": status.get("mode"),
        "configuration_ready": bool(status.get("configuration_ready")),
        "adapter_implemented": bool(status.get("adapter_implemented")),
        "ready_for_checkout": bool(status.get("ready_for_checkout")),
        "missing_config": list(status.get("missing_config") or []),
    }
    return _check(
        "billing_provider_readiness",
        "billing",
        "Billing provider readiness",
        ok=not safe_status["billing_enabled"] or safe_status["ready_for_checkout"],
        message="Billing provider readiness is visible and sanitized.",
        evidence=safe_status,
    )


def build_platform_ops_health_status() -> dict[str, Any]:
    checks = [
        *_database_check(),
        *_config_checks(),
        _billing_check(),
        *_file_checks(),
    ]
    degraded = sum(1 for check in checks if check["status"] != "ok")
    critical_degraded = sum(
        1 for check in checks if check["status"] != "ok" and check.get("severity") == "critical"
    )
    overall_status = "failed" if critical_degraded else ("degraded" if degraded else "ok")
    return {
        "mode": "local_ops_health",
        "ai_used": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "overall_status": overall_status,
        "summary": {
            "total": len(checks),
            "ok": len(checks) - degraded,
            "degraded": degraded,
            "critical_degraded": critical_degraded,
        },
        "checks": checks,
    }

from __future__ import annotations

import argparse
import json
import os
import re
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE_REL = "docs/superpowers/platform-production-env.example"
LAUNCH_DOC_REL = "docs/superpowers/platform-v2-launch-readiness.md"
LEGAL_DOC_REL = "docs/superpowers/platform-legal-copy-draft.md"
HANDOFF_DOC_REL = "docs/superpowers/platform-v2-handoff-status.md"

REQUIRED_ENV_KEYS = {
    "ADMIN_AUTH_ENABLED",
    "PLATFORM_USER_AUTH_ENABLED",
    "PLATFORM_CSRF_ENABLED",
    "DATABASE_PATH",
    "DSA_SECRET_SOURCE",
    "LITELLM_MODEL",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED",
    "ENABLE_FUNDAMENTAL_PIPELINE",
    "ENABLE_CHIP_DISTRIBUTION",
    "DAILY_MARKET_CONTEXT_ENABLED",
    "REALTIME_CACHE_TTL",
    "BILLING_ENABLED",
    "DEBUG",
    "CORS_ALLOW_ALL",
    "LOCAL_LLM_ENABLED",
    "LOCAL_LLM_MAX_CONCURRENT",
}

EXPECTED_SAFE_VALUES = {
    "ADMIN_AUTH_ENABLED": "true",
    "PLATFORM_USER_AUTH_ENABLED": "true",
    "PLATFORM_CSRF_ENABLED": "true",
    "BILLING_ENABLED": "false",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
    "ENABLE_FUNDAMENTAL_PIPELINE": "false",
    "ENABLE_CHIP_DISTRIBUTION": "false",
    "DAILY_MARKET_CONTEXT_ENABLED": "false",
    "DEBUG": "false",
    "CORS_ALLOW_ALL": "false",
}

SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"\bghp_[0-9A-Za-z]{20,}\b"),
    re.compile(r"\bxox[baprs]-[0-9A-Za-z-]{20,}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class ReadinessCheck:
    id: str
    title: str
    category: str
    paths: list[str] = field(default_factory=list)
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "paths": self.paths,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class ReadinessResult:
    check: ReadinessCheck
    status: str
    elapsed_sec: float = 0.0
    output: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check": self.check.to_dict(),
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


def _root(project_root: str | Path | None = None) -> Path:
    return Path(project_root).resolve() if project_root is not None else REPO_ROOT


def build_readiness_checks(*, project_root: str | Path | None = None) -> list[ReadinessCheck]:
    root = str(_root(project_root))
    return [
        ReadinessCheck(
            "prod_env_template",
            "Production configuration template",
            "config",
            paths=[ENV_TEMPLATE_REL],
            evidence=f"{root}/{ENV_TEMPLATE_REL}",
        ),
        ReadinessCheck(
            "safe_config_flags",
            "Safe launch-blocking configuration flags",
            "security",
            paths=[ENV_TEMPLATE_REL],
            evidence="Auth, CSRF, billing, public search, debug, and CORS defaults.",
        ),
        ReadinessCheck(
            "security_scan_rules",
            "Static security boundary scan",
            "security",
            paths=[
                "src/platform_audit.py",
                "apps/dsa-web/src/pages/AdminPage.tsx",
                "src/csrf.py",
                "api/middlewares/auth.py",
                "api/v1/endpoints/billing.py",
            ],
            evidence="Redaction, CSRF, auth middleware, and billing-disabled boundary.",
        ),
        ReadinessCheck(
            "backup_restore_dry_run",
            "SQLite backup and restore dry-run",
            "data",
            paths=[],
            evidence="Uses a temporary source database, backup file, and restored database.",
        ),
        ReadinessCheck(
            "schema_migration_check",
            "Platform schema migration check",
            "data",
            paths=["src/storage.py"],
            evidence="Temporary SQLite schema contains platform tables and history owner column.",
        ),
        ReadinessCheck(
            "launch_readiness_doc",
            "Launch readiness document",
            "docs",
            paths=[LAUNCH_DOC_REL],
            evidence="Release candidate status, blockers, manual decisions, and no-go rules.",
        ),
        ReadinessCheck(
            "legal_copy_draft",
            "Legal and product copy draft",
            "docs",
            paths=[LEGAL_DOC_REL],
            evidence="Informational only, privacy, API key custody, quota, and BYOK risk copy.",
        ),
        ReadinessCheck(
            "dirty_handoff_status",
            "Dirty work handoff status",
            "docs",
            paths=[HANDOFF_DOC_REL],
            evidence="Read-only git status distribution and follow-up packaging notes.",
        ),
    ]


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _contains_secret_like_value(value: str) -> bool:
    return any(pattern.search(value or "") for pattern in SECRET_VALUE_PATTERNS)


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _result(
    check: ReadinessCheck,
    started: float,
    *,
    status: str = "passed",
    output: str = "",
    error: str = "",
    metadata: dict | None = None,
) -> ReadinessResult:
    return ReadinessResult(
        check=check,
        status=status,
        elapsed_sec=time.monotonic() - started,
        output=output,
        error=error,
        metadata=metadata or {},
    )


def _run_prod_env_template_check(check: ReadinessCheck, root: Path, env_file: Path | None) -> ReadinessResult:
    started = time.monotonic()
    path = (env_file or root / ENV_TEMPLATE_REL).resolve()
    if not path.exists():
        return _result(check, started, status="failed", error=f"missing env template: {path}")
    values = _parse_env_file(path)
    missing = sorted(REQUIRED_ENV_KEYS - set(values))
    secret_like_keys = sorted(key for key, value in values.items() if _contains_secret_like_value(value))
    if missing or secret_like_keys:
        return _result(
            check,
            started,
            status="failed",
            error="env template is incomplete or contains secret-like values",
            metadata={"missing_keys": missing, "secret_like_keys": secret_like_keys},
        )
    return _result(check, started, metadata={"checked_keys": sorted(REQUIRED_ENV_KEYS)})


def _run_safe_config_flags_check(check: ReadinessCheck, root: Path, env_file: Path | None) -> ReadinessResult:
    started = time.monotonic()
    path = (env_file or root / ENV_TEMPLATE_REL).resolve()
    if not path.exists():
        return _result(check, started, status="failed", error=f"missing env template: {path}")
    values = {key: value.strip().lower() for key, value in _parse_env_file(path).items()}
    mismatches = {
        key: {"expected": expected, "actual_present": key in values}
        for key, expected in EXPECTED_SAFE_VALUES.items()
        if values.get(key) != expected
    }
    if mismatches:
        return _result(
            check,
            started,
            status="failed",
            error="unsafe or missing launch-blocking config flags",
            metadata={"mismatches": mismatches},
        )
    return _result(check, started, metadata={"safe_flags": sorted(EXPECTED_SAFE_VALUES)})


def _run_security_scan_rules_check(check: ReadinessCheck, root: Path) -> ReadinessResult:
    started = time.monotonic()
    required_markers = {
        "src/platform_audit.py": ["redact_metadata", "[REDACTED]", "SECRET_VALUE_PATTERNS"],
        "apps/dsa-web/src/pages/AdminPage.tsx": ["redactAuditMetadata", "[REDACTED]"],
        "src/csrf.py": ["PLATFORM_CSRF_ENABLED", "require_csrf"],
        "api/middlewares/auth.py": ["_csrf_failure_response", "verify_session", "verify_platform_session"],
        "api/v1/endpoints/billing.py": ["BILLING_ENABLED", "billing_disabled", "invalid_signature"],
    }
    missing: dict[str, list[str]] = {}
    for rel_path, markers in required_markers.items():
        path = root / rel_path
        if not path.exists():
            missing[rel_path] = ["<missing file>"]
            continue
        text = _read_text(path)
        absent = [marker for marker in markers if marker not in text]
        if absent:
            missing[rel_path] = absent
    if missing:
        return _result(
            check,
            started,
            status="failed",
            error="security boundary markers are missing",
            metadata={"missing_markers": missing},
        )
    return _result(check, started, metadata={"files_checked": sorted(required_markers)})


def run_backup_restore_dry_run(temp_dir: Path | None = None) -> ReadinessResult:
    check = build_readiness_checks()[3]
    started = time.monotonic()
    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if temp_dir is None:
        owned_temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        temp_path = Path(owned_temp.name)
    else:
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)

    try:
        source_db = temp_path / "source.sqlite"
        backup_db = temp_path / "backup.sqlite"
        restored_db = temp_path / "restored.sqlite"
        with sqlite3.connect(source_db) as conn:
            conn.execute("CREATE TABLE analysis_history (id INTEGER PRIMARY KEY, code TEXT, summary TEXT)")
            conn.execute(
                "INSERT INTO analysis_history (code, summary) VALUES (?, ?)",
                ("AAPL", "dry-run sample"),
            )
            conn.commit()
        with sqlite3.connect(source_db) as source, sqlite3.connect(backup_db) as backup:
            source.backup(backup)
        if restored_db.exists():
            return _result(check, started, status="failed", error="restored database unexpectedly exists before restore")
        with sqlite3.connect(backup_db) as backup, sqlite3.connect(restored_db) as restored:
            backup.backup(restored)
        with sqlite3.connect(source_db) as source, sqlite3.connect(restored_db) as restored:
            source_count = source.execute("SELECT COUNT(*) FROM analysis_history").fetchone()[0]
            restored_count = restored.execute("SELECT COUNT(*) FROM analysis_history").fetchone()[0]
            restored_summary = restored.execute("SELECT summary FROM analysis_history WHERE code='AAPL'").fetchone()[0]
        if source_count != restored_count or restored_summary != "dry-run sample":
            return _result(check, started, status="failed", error="restored data does not match source dry-run data")
        return _result(
            check,
            started,
            metadata={
                "source_row_count": source_count,
                "restored_row_count": restored_count,
                "temp_dir": str(temp_path),
            },
        )
    except Exception as exc:
        return _result(check, started, status="failed", error=str(exc))
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()


def run_schema_migration_check(temp_dir: Path | None = None) -> ReadinessResult:
    check = build_readiness_checks()[4]
    started = time.monotonic()
    owned_temp: tempfile.TemporaryDirectory[str] | None = None
    if temp_dir is None:
        owned_temp = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        temp_path = Path(owned_temp.name)
    else:
        temp_path = Path(temp_dir)
        temp_path.mkdir(parents=True, exist_ok=True)

    try:
        root_text = str(REPO_ROOT)
        if root_text not in sys.path:
            sys.path.insert(0, root_text)
        from src.config import Config
        from src.storage import DatabaseManager

        db_path = temp_path / "migration-check.sqlite"
        DatabaseManager.reset_instance()
        Config.reset_instance()
        DatabaseManager(db_url=f"sqlite:///{db_path}")
        DatabaseManager.reset_instance()
        required_tables = {
            "platform_users",
            "platform_user_api_keys",
            "platform_usage_events",
            "platform_audit_events",
            "analysis_history",
        }
        with sqlite3.connect(db_path) as conn:
            tables = {
                row[0]
                for row in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            }
            missing_tables = sorted(required_tables - tables)
            history_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(analysis_history)").fetchall()
            }
            api_key_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(platform_user_api_keys)").fetchall()
            }
            usage_columns = {
                row[1]
                for row in conn.execute("PRAGMA table_info(platform_usage_events)").fetchall()
            }
        DatabaseManager.reset_instance()
        Config.reset_instance()
        missing_columns = []
        if "platform_user_id" not in history_columns:
            missing_columns.append("analysis_history.platform_user_id")
        if "encrypted_secret" not in api_key_columns:
            missing_columns.append("platform_user_api_keys.encrypted_secret")
        if "quota_bucket" not in usage_columns:
            missing_columns.append("platform_usage_events.quota_bucket")
        if missing_tables or missing_columns:
            return _result(
                check,
                started,
                status="failed",
                error="platform schema check failed",
                metadata={"missing_tables": missing_tables, "missing_columns": missing_columns},
            )
        return _result(
            check,
            started,
            metadata={
                "tables": sorted(required_tables),
                "analysis_history_columns": sorted(history_columns),
                "api_key_columns": sorted(api_key_columns),
                "usage_columns": sorted(usage_columns),
            },
        )
    except Exception as exc:
        return _result(check, started, status="failed", error=str(exc))
    finally:
        if owned_temp is not None:
            owned_temp.cleanup()


def _run_doc_contains_check(
    check: ReadinessCheck,
    root: Path,
    *,
    required_phrases: Sequence[str],
) -> ReadinessResult:
    started = time.monotonic()
    missing_files = []
    missing_phrases: dict[str, list[str]] = {}
    for rel_path in check.paths:
        path = root / rel_path
        if not path.exists():
            missing_files.append(rel_path)
            continue
        text = _read_text(path)
        absent = [phrase for phrase in required_phrases if phrase not in text]
        if absent:
            missing_phrases[rel_path] = absent
    if missing_files or missing_phrases:
        return _result(
            check,
            started,
            status="failed",
            error="required launch readiness documentation is incomplete",
            metadata={"missing_files": missing_files, "missing_phrases": missing_phrases},
        )
    return _result(check, started, metadata={"paths": check.paths})


def _run_dirty_handoff_check(check: ReadinessCheck, root: Path) -> ReadinessResult:
    started = time.monotonic()
    doc_result = _run_doc_contains_check(
        check,
        root,
        required_phrases=["modified", "untracked", "V1 platform", "do not delete"],
    )
    if doc_result.status != "passed":
        return doc_result
    completed = subprocess.run(
        ["git", "status", "--short", "--untracked-files=all"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(check, started, status="failed", error="git status --short failed")
    lines = [line for line in completed.stdout.splitlines() if line.strip()]
    modified = sum(1 for line in lines if line.startswith(" M") or line.startswith("M "))
    untracked = sum(1 for line in lines if line.startswith("??"))
    return _result(
        check,
        started,
        metadata={"modified_count": modified, "untracked_count": untracked, "total_dirty": len(lines)},
    )


def _run_check(check: ReadinessCheck, root: Path, env_file: Path | None = None) -> ReadinessResult:
    if check.id == "prod_env_template":
        return _run_prod_env_template_check(check, root, env_file)
    if check.id == "safe_config_flags":
        return _run_safe_config_flags_check(check, root, env_file)
    if check.id == "security_scan_rules":
        return _run_security_scan_rules_check(check, root)
    if check.id == "backup_restore_dry_run":
        return run_backup_restore_dry_run()
    if check.id == "schema_migration_check":
        return run_schema_migration_check()
    if check.id == "launch_readiness_doc":
        return _run_doc_contains_check(
            check,
            root,
            required_phrases=["V1 completed", "V2 before launch", "No-go", "Manual decisions"],
        )
    if check.id == "legal_copy_draft":
        return _run_doc_contains_check(
            check,
            root,
            required_phrases=[
                "not investment advice",
                "privacy",
                "API Key custody",
                "BYOK",
                "quota",
            ],
        )
    if check.id == "dirty_handoff_status":
        return _run_dirty_handoff_check(check, root)
    return ReadinessResult(check=check, status="failed", error="unknown check id")


def run_readiness_checks(
    *,
    project_root: str | Path | None = None,
    env_file: str | Path | None = None,
    only: Iterable[str] | None = None,
) -> list[ReadinessResult]:
    root = _root(project_root)
    selected_ids = set(only or [])
    env_path = Path(env_file).resolve() if env_file is not None else None
    checks = build_readiness_checks(project_root=root)
    return [
        _run_check(check, root, env_path)
        for check in checks
        if not selected_ids or check.id in selected_ids
    ]


def _print_text_report(results: Sequence[ReadinessResult]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{marker} {result.check.id}: {result.check.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            safe_metadata = {
                key: value
                for key, value in result.metadata.items()
                if key not in {"env_values", "raw_output"}
            }
            if safe_metadata:
                print(f"  metadata: {json.dumps(safe_metadata, ensure_ascii=False)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run DSA Platform V2 launch-readiness checks")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--env-file", default=None, help="Optional env file to scan instead of the safe template")
    parser.add_argument("--only", action="append", default=[], help="Run only a specific check id; can be repeated")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_readiness_checks(
        project_root=args.project_root,
        env_file=args.env_file,
        only=args.only,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

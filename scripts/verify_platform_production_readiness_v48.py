import argparse
import json
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


OK_MARKER = "DSA_PLATFORM_PRODUCTION_READINESS_V48_OK"
REPO_ROOT = Path(__file__).resolve().parents[1]

REQUIRED_FILES = (
    "src/services/production_readiness.py",
    "api/v1/endpoints/platform.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/pages/AdminPage.tsx",
    "apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx",
    "apps/dsa-web/src/api/__tests__/platform.test.ts",
    "tests/test_platform_production_readiness_v48.py",
    "docs/superpowers/plans/2026-07-05-dsa-production-readiness-v48.md",
)

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"\bAIza[0-9A-Za-z_-]{20,}\b"),
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
)


@dataclass(frozen=True)
class VerifyResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
        }


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict | None = None,
) -> VerifyResult:
    return VerifyResult(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run_required_files_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "V48 production readiness files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "V48 production readiness files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_static_markers_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    markers = {
        "src/services/production_readiness.py": [
            "production_preflight",
            "real_payment_disabled",
            "market_data_license_not_approved",
            "not_investment_advice",
        ],
        "api/v1/endpoints/platform.py": [
            "/admin/production-readiness",
            "build_production_readiness_status",
            "admin_production_readiness_viewed",
        ],
        "apps/dsa-web/src/api/platform.ts": [
            "PlatformProductionReadinessResponse",
            "adminProductionReadiness",
            "/api/v1/platform/admin/production-readiness",
        ],
        "apps/dsa-web/src/pages/AdminPage.tsx": [
            "Production readiness",
            "Launch decision",
            "adminProductionReadiness",
        ],
        "docs/superpowers/plans/2026-07-05-dsa-production-readiness-v48.md": [
            "No real payment",
            "GO/NO-GO",
            "DSA_PLATFORM_PRODUCTION_READINESS_V48_OK",
        ],
    }
    missing: dict[str, list[str]] = {}
    for rel_path, expected in markers.items():
        text = _read_text(root / rel_path) if (root / rel_path).exists() else ""
        missing_markers = [marker for marker in expected if marker not in text]
        if missing_markers:
            missing[rel_path] = missing_markers
    if missing:
        return _result(
            "static_markers_present",
            "V48 source markers are present",
            started,
            status="failed",
            error="required static markers are missing",
            metadata={"missing_markers": missing},
        )
    return _result(
        "static_markers_present",
        "V48 source markers are present",
        started,
        metadata={"checked_files": sorted(markers)},
    )


def _run_secret_redaction_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    secret = "sk-v48-verifier-secret-must-not-leak"
    env_updates = {
        "ADMIN_AUTH_ENABLED": "true",
        "PLATFORM_USER_AUTH_ENABLED": "true",
        "PLATFORM_CSRF_ENABLED": "true",
        "CORS_ALLOW_ALL": "false",
        "DEBUG": "false",
        "BILLING_ENABLED": "false",
        "LITELLM_API_KEY": secret,
    }
    current = os.environ.copy()
    current.update(env_updates)
    code = (
        "import json\n"
        "from src.services.production_readiness import build_production_readiness_status\n"
        "print(json.dumps(build_production_readiness_status(), ensure_ascii=False))\n"
    )
    completed = subprocess.run(
        [os.sys.executable, "-c", code],
        cwd=root,
        env=current,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "secret_redaction",
            "Production readiness payload redacts secrets",
            started,
            status="failed",
            error="builder subprocess failed",
            metadata={"stderr_tail": completed.stderr[-800:]},
        )
    leaked_patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(completed.stdout)]
    leaked_tokens = [value for value in (secret, "LITELLM_API_KEY") if value in completed.stdout]
    if leaked_patterns or leaked_tokens:
        return _result(
            "secret_redaction",
            "Production readiness payload redacts secrets",
            started,
            status="failed",
            error="secret-like values leaked in payload",
            metadata={"leaked_patterns": leaked_patterns, "leaked_tokens": leaked_tokens},
        )
    return _result(
        "secret_redaction",
        "Production readiness payload redacts secrets",
        started,
        metadata={"payload_bytes": len(completed.stdout.encode("utf-8"))},
    )


def _run_unittest_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    completed = subprocess.run(
        [os.sys.executable, "-m", "unittest", "tests.test_platform_production_readiness_v48"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "v48_unittests",
            "V48 production readiness backend tests pass",
            started,
            status="failed",
            error="V48 unittest failed",
            metadata={"stdout_tail": completed.stdout[-800:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "v48_unittests",
        "V48 production readiness backend tests pass",
        started,
        metadata={"stderr_tail": completed.stderr[-800:]},
    )


def run_checks(*, project_root: str | Path | None = None) -> list[VerifyResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    return [
        _run_required_files_check(root),
        _run_static_markers_check(root),
        _run_secret_redaction_check(root),
        _run_unittest_check(root),
    ]


def _print_text_report(results: Sequence[VerifyResult]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")
    if all(result.status == "passed" for result in results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA production readiness V48 package")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_checks(project_root=args.project_root)
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

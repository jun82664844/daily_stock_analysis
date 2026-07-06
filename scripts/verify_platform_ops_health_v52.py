from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_OPS_HEALTH_V52_OK"

REQUIRED_FILES = (
    "src/services/platform_ops_health.py",
    "api/v1/endpoints/platform.py",
    "tests/test_platform_ops_health_v52.py",
    "docs/superpowers/plans/2026-07-05-dsa-ops-health-v52.md",
)

REQUIRED_MARKERS = {
    "src/services/platform_ops_health.py": (
        "build_platform_ops_health_status",
        "local_ops_health",
        "database_reachable",
        "backup_runner_available",
        "billing_provider_readiness",
        "ai_used",
    ),
    "api/v1/endpoints/platform.py": (
        "/admin/ops-health",
        "build_platform_ops_health_status",
        "admin_ops_health_viewed",
    ),
    "tests/test_platform_ops_health_v52.py": (
        "sk_test_v52_should_not_leak",
        "/api/v1/platform/admin/ops-health",
        "local_ops_health",
    ),
    "docs/superpowers/plans/2026-07-05-dsa-ops-health-v52.md": (
        "DSA_PLATFORM_OPS_HEALTH_V52_OK",
        "Admin-only",
        "Read-only",
    ),
}


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


def _run_required_files_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "V52 ops health files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "V52 ops health files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_static_markers_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing: dict[str, list[str]] = {}
    for rel_path, markers in REQUIRED_MARKERS.items():
        path = root / rel_path
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        absent = [marker for marker in markers if marker not in text]
        if absent:
            missing[rel_path] = absent
    if missing:
        return _result(
            "static_markers_present",
            "V52 source markers are present",
            started,
            status="failed",
            error="required markers are missing",
            metadata={"missing_markers": missing},
        )
    return _result(
        "static_markers_present",
        "V52 source markers are present",
        started,
        metadata={"checked_files": sorted(REQUIRED_MARKERS)},
    )


def _run_secret_redaction_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    secret = "sk_test_v52_should_not_leak"
    env = os.environ.copy()
    env.update(
        {
            "BILLING_ENABLED": "true",
            "BILLING_PROVIDER": "stripe",
            "BILLING_STRIPE_SECRET_KEY": secret,
            "DEBUG": "false",
            "CORS_ALLOW_ALL": "false",
            "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
        }
    )
    code = (
        "import json;"
        "from src.services.platform_ops_health import build_platform_ops_health_status;"
        "print(json.dumps(build_platform_ops_health_status(), sort_keys=True))"
    )
    completed = subprocess.run(
        [sys.executable, "-c", code],
        cwd=root,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output = completed.stdout + completed.stderr
    if completed.returncode != 0:
        return _result(
            "secret_redaction",
            "Ops health payload redacts secrets",
            started,
            status="failed",
            error="ops health script failed",
            metadata={"stderr_tail": completed.stderr[-800:]},
        )
    if secret in output:
        return _result(
            "secret_redaction",
            "Ops health payload redacts secrets",
            started,
            status="failed",
            error="secret-like value leaked in ops health payload",
            metadata={"output_tail": output[-800:]},
        )
    return _result(
        "secret_redaction",
        "Ops health payload redacts secrets",
        started,
        metadata={"payload_bytes": len(completed.stdout.encode("utf-8"))},
    )


def _run_unittest_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_platform_ops_health_v52"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "v52_unittests",
            "V52 ops health tests pass",
            started,
            status="failed",
            error="V52 unittest failed",
            metadata={"stdout_tail": completed.stdout[-800:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "v52_unittests",
        "V52 ops health tests pass",
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
    parser = argparse.ArgumentParser(description="Verify DSA ops health V52 package")
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

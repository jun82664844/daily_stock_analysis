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
OK_MARKER = "DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK"

REQUIRED_FILES = (
    "src/billing/payment_provider.py",
    "api/v1/endpoints/billing.py",
    "src/services/production_readiness.py",
    "tests/test_billing_provider_boundary_v49.py",
    "docs/superpowers/plans/2026-07-05-dsa-billing-provider-boundary-v49.md",
)

REQUIRED_MARKERS = {
    "src/billing/payment_provider.py": (
        "get_payment_provider_status",
        "REAL_PROVIDER_REQUIREMENTS",
        "real_provider_configured_not_implemented",
        "BILLING_STRIPE_WEBHOOK_SECRET",
    ),
    "api/v1/endpoints/billing.py": (
        "billing_provider_not_ready",
        "billing_provider_adapter_not_implemented",
        "provider_readiness",
    ),
    "src/services/production_readiness.py": (
        "get_payment_provider_status",
        "real_payment_provider_not_ready",
        "adapter_implemented",
    ),
    "tests/test_billing_provider_boundary_v49.py": (
        "sk_test_v49_should_not_leak",
        "billing_provider_not_ready",
        "billing_provider_adapter_not_implemented",
    ),
    "docs/superpowers/plans/2026-07-05-dsa-billing-provider-boundary-v49.md": (
        "No real payment",
        "DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK",
        "Do not commit real API Key",
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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run_required_files_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "V49 billing provider boundary files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "V49 billing provider boundary files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_static_markers_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing: dict[str, list[str]] = {}
    for rel_path, markers in REQUIRED_MARKERS.items():
        path = root / rel_path
        text = _read_text(path) if path.exists() else ""
        absent = [marker for marker in markers if marker not in text]
        if absent:
            missing[rel_path] = absent
    if missing:
        return _result(
            "static_markers_present",
            "V49 source markers are present",
            started,
            status="failed",
            error="required markers are missing",
            metadata={"missing_markers": missing},
        )
    return _result(
        "static_markers_present",
        "V49 source markers are present",
        started,
        metadata={"checked_files": sorted(REQUIRED_MARKERS)},
    )


def _run_secret_redaction_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    secret = "sk_test_v49_should_not_leak"
    env = os.environ.copy()
    env.update(
        {
            "BILLING_ENABLED": "true",
            "BILLING_PROVIDER": "stripe",
            "BILLING_STRIPE_SECRET_KEY": secret,
            "BILLING_STRIPE_WEBHOOK_SECRET": "whsec_v49_should_not_leak",
        }
    )
    code = (
        "import json;"
        "from src.billing.payment_provider import get_payment_provider_status;"
        "print(json.dumps(get_payment_provider_status(), sort_keys=True))"
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
            "Provider readiness status redacts secrets",
            started,
            status="failed",
            error="provider status script failed",
            metadata={"stderr_tail": completed.stderr[-800:]},
        )
    if secret in output or "whsec_v49_should_not_leak" in output:
        return _result(
            "secret_redaction",
            "Provider readiness status redacts secrets",
            started,
            status="failed",
            error="secret-like value leaked in provider status",
            metadata={"output_tail": output[-800:]},
        )
    return _result(
        "secret_redaction",
        "Provider readiness status redacts secrets",
        started,
        metadata={"payload_bytes": len(completed.stdout.encode("utf-8"))},
    )


def _run_unittest_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_billing_provider_boundary_v49"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "v49_unittests",
            "V49 billing provider boundary tests pass",
            started,
            status="failed",
            error="V49 unittest failed",
            metadata={"stdout_tail": completed.stdout[-800:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "v49_unittests",
        "V49 billing provider boundary tests pass",
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
    parser = argparse.ArgumentParser(description="Verify DSA billing provider boundary V49 package")
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

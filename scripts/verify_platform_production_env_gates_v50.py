from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE = "docs/superpowers/platform-production-env.example"
OK_MARKER = "DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK"

REQUIRED_SAFE_VALUES = {
    "ADMIN_AUTH_ENABLED": "true",
    "PLATFORM_USER_AUTH_ENABLED": "true",
    "PLATFORM_CSRF_ENABLED": "true",
    "BILLING_ENABLED": "false",
    "BILLING_PROVIDER": "disabled",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
    "ENABLE_FUNDAMENTAL_PIPELINE": "false",
    "ENABLE_CHIP_DISTRIBUTION": "false",
    "DAILY_MARKET_CONTEXT_ENABLED": "false",
    "DEBUG": "false",
    "CORS_ALLOW_ALL": "false",
    "LOCAL_LLM_ENABLED": "false",
    "DSA_REAL_PAYMENT_APPROVED": "false",
    "DSA_PAYMENT_WEBHOOK_APPROVED": "false",
    "DSA_PRODUCTION_DOMAIN_APPROVED": "false",
    "DSA_PRODUCTION_HTTPS_APPROVED": "false",
    "DSA_PRODUCTION_WAF_APPROVED": "false",
    "DSA_MARKET_DATA_LICENSE_APPROVED": "false",
    "DSA_LEGAL_TERMS_APPROVED": "false",
    "DSA_PRIVACY_POLICY_APPROVED": "false",
    "DSA_MONITORING_APPROVED": "false",
    "DSA_BACKUP_RESTORE_DRILL_APPROVED": "false",
    "DSA_ANALYSIS_NOT_INVESTMENT_ADVICE": "true",
}

BLANK_SECRET_PLACEHOLDERS = {
    "BILLING_STRIPE_SECRET_KEY",
    "BILLING_STRIPE_WEBHOOK_SECRET",
    "BILLING_STRIPE_PRICE_PRO",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"\bwhsec_[A-Za-z0-9._-]{8,}\b"),
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


def _parse_env_file(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def _run_env_safe_defaults_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    path = root / ENV_TEMPLATE
    if not path.exists():
        return _result(
            "env_template_exists",
            "Production env template exists",
            started,
            status="failed",
            error="env template is missing",
        )
    values = _parse_env_file(path)
    missing = sorted(set(REQUIRED_SAFE_VALUES) - set(values))
    unsafe = {
        key: {"expected": expected, "actual_present": key in values}
        for key, expected in REQUIRED_SAFE_VALUES.items()
        if values.get(key, "").lower() != expected
    }
    if missing or unsafe:
        return _result(
            "env_safe_defaults",
            "Production env template has explicit safe launch gates",
            started,
            status="failed",
            error="env template is missing safe defaults",
            metadata={"missing_keys": missing, "unsafe_values": unsafe},
        )
    return _result(
        "env_safe_defaults",
        "Production env template has explicit safe launch gates",
        started,
        metadata={"checked_keys": sorted(REQUIRED_SAFE_VALUES)},
    )


def _run_blank_provider_placeholders_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    path = root / ENV_TEMPLATE
    values = _parse_env_file(path)
    missing = sorted(key for key in BLANK_SECRET_PLACEHOLDERS if key not in values)
    not_blank = sorted(key for key in BLANK_SECRET_PLACEHOLDERS if values.get(key, "") != "")
    text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
    leaked_patterns = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
    if missing or not_blank or leaked_patterns:
        return _result(
            "blank_provider_placeholders",
            "Real provider placeholders are blank and secret-free",
            started,
            status="failed",
            error="real provider placeholders are unsafe",
            metadata={"missing": missing, "not_blank": not_blank, "leaked_patterns": leaked_patterns},
        )
    return _result(
        "blank_provider_placeholders",
        "Real provider placeholders are blank and secret-free",
        started,
        metadata={"checked_keys": sorted(BLANK_SECRET_PLACEHOLDERS)},
    )


def _run_v2_readiness_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "scripts/verify_platform_v2_readiness.py"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "v2_readiness",
            "V2 readiness verifier accepts production env gates",
            started,
            status="failed",
            error="V2 readiness verifier failed",
            metadata={"stdout_tail": completed.stdout[-1200:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "v2_readiness",
        "V2 readiness verifier accepts production env gates",
        started,
        metadata={"stdout_tail": completed.stdout[-800:]},
    )


def _run_unittest_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_platform_production_env_gates_v50"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "v50_unittests",
            "V50 production env gate tests pass",
            started,
            status="failed",
            error="V50 unittest failed",
            metadata={"stdout_tail": completed.stdout[-800:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "v50_unittests",
        "V50 production env gate tests pass",
        started,
        metadata={"stderr_tail": completed.stderr[-800:]},
    )


def run_checks(*, project_root: str | Path | None = None) -> list[VerifyResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    return [
        _run_env_safe_defaults_check(root),
        _run_blank_provider_placeholders_check(root),
        _run_v2_readiness_check(root),
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
    parser = argparse.ArgumentParser(description="Verify DSA production env gates V50 package")
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

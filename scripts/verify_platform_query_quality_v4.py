from __future__ import annotations

import json
import os
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_QUERY_QUALITY_V4_OK"

REQUIRED_FILES = (
    "src/services/basic_query_service.py",
    "src/services/stock_code_utils.py",
    "api/middlewares/auth.py",
    "api/v1/endpoints/stocks.py",
    "api/v1/schemas/basic_query.py",
    "tests/test_platform_query_quality_v4.py",
    "tests/test_basic_query_no_ai.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
)

UNITTEST_MODULES = (
    "tests.test_platform_query_quality_v4",
    "tests.test_basic_query_no_ai",
    "tests.test_market_data_cache",
    "tests.test_platform_ai_feature_quota",
)


@dataclass(frozen=True)
class CheckResult:
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
) -> CheckResult:
    return CheckResult(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _read_text(root: Path, rel_path: str) -> str:
    return (root / rel_path).read_text(encoding="utf-8", errors="replace")


def _run_required_files_check(root: Path) -> CheckResult:
    started = time.monotonic()
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        return _result(
            "required_files_present",
            "Query Quality V4 files exist",
            started,
            status="failed",
            error="required files missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "Query Quality V4 files exist",
        started,
        metadata={"checked_files": list(REQUIRED_FILES)},
    )


def _run_static_boundary_check(root: Path) -> CheckResult:
    started = time.monotonic()
    basic_query = _read_text(root, "src/services/basic_query_service.py")
    auth_middleware = _read_text(root, "api/middlewares/auth.py")
    stocks_api = _read_text(root, "api/v1/endpoints/stocks.py")
    basic_query_tests = _read_text(root, "tests/test_basic_query_no_ai.py")
    frontend = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    combined = "\n".join([basic_query, auth_middleware, stocks_api, basic_query_tests, frontend])
    missing_markers = [
        marker
        for marker in (
            "a_share_market_data",
            "us_market_data",
            "crypto_market_data",
            "stale_quote",
            "missing_quote",
            "ai_used\": False",
            "basic-query-degradation",
            "_public_no_ai_query_path",
            "request.method.upper() != \"GET\"",
            "path.startswith(\"/api/v1/stocks/\")",
            "path.endswith(\"/snapshot\")",
            "test_snapshot_is_public_without_platform_login",
            "analysis_service.assert_not_called()",
        )
        if marker not in combined
    ]
    unsafe_markers = [
        marker
        for marker in (
            "SEARXNG_PUBLIC_INSTANCES_ENABLED=true",
            "sk-live-",
            "stripe_live",
        )
        if marker.lower() in combined.lower()
    ]
    if missing_markers or unsafe_markers:
        return _result(
            "static_query_quality_boundaries",
            "Market lanes and degradation boundaries are present",
            started,
            status="failed",
            error="static query-quality boundary check failed",
            metadata={"missing_markers": missing_markers, "unsafe_markers": unsafe_markers},
        )
    return _result(
        "static_query_quality_boundaries",
        "Market lanes and degradation boundaries are present",
        started,
        metadata={
            "markers": [
                "a_share_market_data",
                "us_market_data",
                "crypto_market_data",
                "_public_no_ai_query_path",
            ]
        },
    )


def _run_unittest_check(root: Path) -> CheckResult:
    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("SEARXNG_PUBLIC_INSTANCES_ENABLED", "false")
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", *UNITTEST_MODULES],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        env=env,
    )
    if completed.returncode != 0:
        return _result(
            "query_quality_unittests",
            "Query Quality V4 backend tests pass",
            started,
            status="failed",
            error="unittest command failed",
            metadata={
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
                "modules": list(UNITTEST_MODULES),
            },
        )
    return _result(
        "query_quality_unittests",
        "Query Quality V4 backend tests pass",
        started,
        metadata={"modules": list(UNITTEST_MODULES), "stderr_tail": completed.stderr[-1000:]},
    )


def run_query_quality_checks(*, project_root: str | Path | None = None) -> list[CheckResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    return [
        _run_required_files_check(root),
        _run_static_boundary_check(root),
        _run_unittest_check(root),
    ]


def _print_text_report(results: Sequence[CheckResult]) -> None:
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
    del argv
    results = run_query_quality_checks()
    _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

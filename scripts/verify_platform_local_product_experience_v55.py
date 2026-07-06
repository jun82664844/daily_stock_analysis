from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_LOCAL_PRODUCT_EXPERIENCE_V55_OK"

REQUIRED_FILES = (
    "src/services/basic_query_service.py",
    "api/v1/schemas/basic_query.py",
    "tests/test_basic_query_no_ai.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md",
)

STATIC_MARKERS = (
    "guest-query-entry",
    "guest-example-AAPL",
    "guest-example-600519",
    "guest-example-00700.HK",
    "guest-example-BTC-USD",
    "No login required",
    "retention_brief",
    "_retention_brief_payload",
    "BasicRetentionBriefPayload",
    "retentionBrief",
    "basic-query-retention-brief",
    "no_ai_retention_rules",
    "test_no_ai_snapshot_includes_retention_brief",
    "analysis_service.assert_not_called()",
    "guest-conversion-guide",
    "guest-guide-register",
    "Login is optional",
    "save history",
    "watchlist",
    "weekly quota",
    "lets guests query first and then shows a non-blocking login guide",
    "not investment advice",
)

UNITTEST_MODULES = (
    "tests.test_basic_query_no_ai",
    "tests.test_platform_local_product_experience_v55",
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


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _run_required_files_check(root: Path) -> CheckResult:
    started = time.monotonic()
    missing = [rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists()]
    if missing:
        return _result(
            "required_files_present",
            "V55 local product experience files exist",
            started,
            status="failed",
            error="required files missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "V55 local product experience files exist",
        started,
        metadata={"checked_files": list(REQUIRED_FILES)},
    )


def _run_static_boundary_check(root: Path) -> CheckResult:
    started = time.monotonic()
    texts = []
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if path.exists():
            texts.append(_read_text(path))
    combined = "\n".join(texts)
    missing_markers = [marker for marker in STATIC_MARKERS if marker not in combined]
    unsafe_markers = []
    for marker in (
        "SEARXNG_PUBLIC_INSTANCES_ENABLED=true",
        "sk-live-",
        "stripe_live",
        "BILLING_PROVIDER=stripe",
    ):
        marker_lower = marker.lower()
        for line in combined.splitlines():
            line_lower = line.lower()
            if marker_lower not in line_lower:
                continue
            if "not.tohavetextcontent" in line_lower or "assertnotin" in line_lower or "not in" in line_lower:
                continue
            unsafe_markers.append(marker)
            break
    if missing_markers or unsafe_markers:
        return _result(
            "static_product_experience_boundaries",
            "Guest-first free product experience boundaries are present",
            started,
            status="failed",
            error="static V55 product experience check failed",
            metadata={"missing_markers": missing_markers, "unsafe_markers": unsafe_markers},
        )
    return _result(
        "static_product_experience_boundaries",
        "Guest-first free product experience boundaries are present",
        started,
        metadata={"markers": list(STATIC_MARKERS)},
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
            "v55_unittests",
            "V55 backend and verifier tests pass",
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
        "v55_unittests",
        "V55 backend and verifier tests pass",
        started,
        metadata={"modules": list(UNITTEST_MODULES), "stderr_tail": completed.stderr[-1000:]},
    )


def _json_get(url: str, timeout_sec: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _run_live_check(live_url: str) -> CheckResult:
    started = time.monotonic()
    base = live_url.rstrip("/")
    try:
        health = _json_get(f"{base}/health", timeout_sec=10)
        snapshot = _json_get(
            f"{base}/api/v1/stocks/{urllib.parse.quote('AAPL', safe='')}/snapshot",
            timeout_sec=30,
        )
        intelligence = snapshot.get("intelligence") or {}
        retention = intelligence.get("retention_brief") or {}
        failures: list[str] = []
        if snapshot.get("ai_used") is not False:
            failures.append("AAPL: ai_used is not false")
        if not retention:
            failures.append("AAPL: missing retention_brief")
        for key in ("headline", "why_it_matters", "support_resistance", "next_steps", "upgrade_hint", "boundary"):
            if retention.get(key) in (None, "", []):
                failures.append(f"AAPL: retention_brief.{key} missing")
        if "not investment advice" not in str(retention.get("boundary") or ""):
            failures.append("AAPL: retention boundary missing investment-advice copy")
        if failures:
            return _result(
                "live_product_experience_api",
                "Live 8018 AAPL no-AI retention brief is usable",
                started,
                status="failed",
                error="live product experience check failed",
                metadata={"failures": failures, "health": health},
            )
        return _result(
            "live_product_experience_api",
            "Live 8018 AAPL no-AI retention brief is usable",
            started,
            metadata={
                "health": health,
                "stock_code": snapshot.get("stock_code"),
                "ai_used": snapshot.get("ai_used"),
                "retention_source": retention.get("source"),
            },
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _result(
            "live_product_experience_api",
            "Live 8018 AAPL no-AI retention brief is usable",
            started,
            status="failed",
            error=str(exc),
            metadata={"live_url": live_url},
        )


def run_local_product_experience_checks(
    *,
    project_root: Path = REPO_ROOT,
    run_tests: bool = True,
    live_url: str | None = None,
) -> list[CheckResult]:
    root = project_root.resolve()
    results = [
        _run_required_files_check(root),
        _run_static_boundary_check(root),
    ]
    if run_tests:
        results.append(_run_unittest_check(root))
    if live_url:
        results.append(_run_live_check(live_url))
    return results


def _print_results(results: Sequence[CheckResult]) -> int:
    failed = False
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")
        failed = failed or result.status != "passed"
    if not failed:
        print(OK_MARKER)
    return 1 if failed else 0


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V55 local product experience.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--skip-tests", action="store_true")
    parser.add_argument("--live-url", default=None)
    args = parser.parse_args(argv)
    results = run_local_product_experience_checks(
        project_root=Path(args.project_root),
        run_tests=not args.skip_tests,
        live_url=args.live_url,
    )
    return _print_results(results)


if __name__ == "__main__":
    raise SystemExit(main())

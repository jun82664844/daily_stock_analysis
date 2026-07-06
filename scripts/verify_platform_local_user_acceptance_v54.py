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
OK_MARKER = "DSA_PLATFORM_LOCAL_USER_ACCEPTANCE_V54_OK"

REQUIRED_FILES = (
    "src/services/basic_query_service.py",
    "tests/test_basic_query_no_ai.py",
    "tests/test_platform_query_quality_v4.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md",
)

STATIC_MARKERS = (
    "a_share_market_data",
    "us_market_data",
    "hk_market_data",
    "crypto_market_data",
    "no_ai_low_cost",
    "quote_from_history_close",
    "_quote_from_history_close_fallback",
    "test_snapshot_is_public_without_platform_login",
    "test_hk_snapshot_uses_history_close_when_realtime_quote_is_missing",
    "analysis_service.assert_not_called()",
    "basic-query-primary-summary",
    "basic-query-free-report",
    "basic-query-mini-chart",
    "basic-query-signal-score",
    "basic-query-intelligence-panel",
    "basic-query-market-brief",
    "basic-query-free-insights",
    "basic-query-peer-comparison",
    "basic-query-watch-points",
    "basic-query-product-brief",
    "basic-query-user-guardrails",
    "not investment advice",
)

UNITTEST_MODULES = (
    "tests.test_basic_query_no_ai",
    "tests.test_platform_query_quality_v4",
    "tests.test_platform_local_user_acceptance_v54",
)

LIVE_SYMBOLS = (
    ("AAPL", "us_market_data"),
    ("600519", "a_share_market_data"),
    ("00700.HK", "hk_market_data"),
    ("BTC-USD", "crypto_market_data"),
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
            "V54 local user acceptance files exist",
            started,
            status="failed",
            error="required files missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "V54 local user acceptance files exist",
        started,
        metadata={"checked_files": list(REQUIRED_FILES)},
    )


def _run_static_boundary_check(root: Path) -> CheckResult:
    started = time.monotonic()
    existing_texts = []
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if path.exists():
            existing_texts.append(_read_text(path))
    combined = "\n".join(existing_texts)
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
            "static_user_acceptance_boundaries",
            "Anonymous no-AI query and free report boundaries are present",
            started,
            status="failed",
            error="static V54 boundary check failed",
            metadata={"missing_markers": missing_markers, "unsafe_markers": unsafe_markers},
        )
    return _result(
        "static_user_acceptance_boundaries",
        "Anonymous no-AI query and free report boundaries are present",
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
            "v54_unittests",
            "V54 backend no-AI and verifier tests pass",
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
        "v54_unittests",
        "V54 backend no-AI and verifier tests pass",
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
        snapshots: dict[str, dict] = {}
        failures: list[str] = []
        for symbol, expected_lane in LIVE_SYMBOLS:
            snapshot = _json_get(f"{base}/api/v1/stocks/{urllib.parse.quote(symbol, safe='')}/snapshot", timeout_sec=30)
            route = snapshot.get("route") or {}
            quote = snapshot.get("quote") or {}
            intelligence = snapshot.get("intelligence") or {}
            if snapshot.get("ai_used") is not False:
                failures.append(f"{symbol}: ai_used is not false")
            if route.get("data_source_lane") != expected_lane:
                failures.append(f"{symbol}: lane {route.get('data_source_lane')} != {expected_lane}")
            if not intelligence:
                failures.append(f"{symbol}: missing no-AI intelligence")
            if symbol in {"AAPL", "00700.HK"} and quote.get("current_price") in (None, ""):
                failures.append(f"{symbol}: missing display price")
            snapshots[symbol] = {
                "market": snapshot.get("market"),
                "lane": route.get("data_source_lane"),
                "ai_used": snapshot.get("ai_used"),
                "price_present": quote.get("current_price") not in (None, ""),
                "degradation": (snapshot.get("degradation") or {}).get("status"),
            }
        if failures:
            return _result(
                "live_anonymous_snapshot_api",
                "Live 8018 anonymous no-AI APIs are usable",
                started,
                status="failed",
                error="live anonymous snapshot check failed",
                metadata={"failures": failures, "health": health, "snapshots": snapshots},
            )
        return _result(
            "live_anonymous_snapshot_api",
            "Live 8018 anonymous no-AI APIs are usable",
            started,
            metadata={"health": health, "snapshots": snapshots},
        )
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError) as exc:
        return _result(
            "live_anonymous_snapshot_api",
            "Live 8018 anonymous no-AI APIs are usable",
            started,
            status="failed",
            error=f"live check failed: {exc}",
        )


def run_local_user_acceptance_checks(
    *,
    project_root: str | Path | None = None,
    run_tests: bool = True,
    live_url: str | None = None,
) -> list[CheckResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    results = [
        _run_required_files_check(root),
        _run_static_boundary_check(root),
    ]
    if run_tests:
        results.append(_run_unittest_check(root))
    if live_url:
        results.append(_run_live_check(live_url))
    return results


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
    parser = argparse.ArgumentParser(description="Verify DSA V54 local user acceptance")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--skip-tests", action="store_true", help="Skip backend unittest gate")
    parser.add_argument("--live-url", default="", help="Optional live DSA base URL, for example http://127.0.0.1:8018")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_user_acceptance_checks(
        project_root=args.project_root,
        run_tests=not args.skip_tests,
        live_url=args.live_url or None,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))

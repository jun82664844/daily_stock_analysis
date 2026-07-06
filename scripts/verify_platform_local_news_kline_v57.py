from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_LOCAL_NEWS_KLINE_V57_OK"

REQUIRED_FILES = (
    "src/services/basic_query_service.py",
    "api/v1/schemas/basic_query.py",
    "tests/test_basic_query_no_ai.py",
    "tests/test_platform_local_news_kline_v57.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/api/__tests__/stocks.test.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-06-dsa-v57-news-kline-forecast-lab.md",
)

STATIC_MARKERS = (
    "news_center",
    "_news_center_payload",
    "BasicNewsCenterPayload",
    "BasicNewsCenterItemPayload",
    "no_ai_news_center_rules",
    "public_search_used",
    "kline_forecast",
    "_kline_forecast_payload",
    "BasicKlineForecastPayload",
    "BasicKlineForecastScenarioPayload",
    "local_kline_rules_kronos_ready",
    "Kronos adapter ready",
    "kronos_model_used",
    "test_no_ai_snapshot_includes_news_center_and_kline_forecast_lab",
    "analysis_service.assert_not_called()",
    "newsCenter",
    "publicSearchUsed",
    "klineForecast",
    "adapterStatus",
    "kronosModelUsed",
    "basic-query-news-center",
    "basic-query-kline-forecast-lab",
    "basic-query-premium-feature-ladder",
    "Kronos-ready",
    "No public search",
    "Premium",
    "not investment advice",
    OK_MARKER,
)

UNITTEST_MODULES = (
    "tests.test_basic_query_no_ai",
    "tests.test_platform_local_news_kline_v57",
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
            "v57_required_files_present",
            "V57 local news and K-line files exist",
            started,
            status="failed",
            error="required files missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v57_required_files_present",
        "V57 local news and K-line files exist",
        started,
        metadata={"checked_files": list(REQUIRED_FILES)},
    )


def _run_static_boundary_check(root: Path) -> CheckResult:
    started = time.monotonic()
    texts: list[str] = []
    for rel_path in REQUIRED_FILES:
        path = root / rel_path
        if path.exists():
            texts.append(_read_text(path))
    combined = "\n".join(texts)
    missing = [marker for marker in STATIC_MARKERS if marker not in combined]
    unsafe = []
    for marker in (
        "SEARXNG_PUBLIC_INSTANCES_ENABLED=true",
        "sk-live-",
        "stripe_live",
        "BILLING_PROVIDER=stripe",
        "kronos_model_used\": true",
        "public_search_used\": true",
    ):
        marker_lower = marker.lower()
        for line in combined.splitlines():
            line_lower = line.lower()
            if marker_lower not in line_lower:
                continue
            if "not.tohavetextcontent" in line_lower or "assertnotin" in line_lower or "not in" in line_lower:
                continue
            unsafe.append(marker)
            break
    if missing or unsafe:
        return _result(
            "v57_static_news_kline_boundaries",
            "V57 no-AI news and K-line boundaries are present",
            started,
            status="failed",
            error="static V57 news/kline check failed",
            metadata={"missing_markers": missing, "unsafe_markers": unsafe},
        )
    return _result(
        "v57_static_news_kline_boundaries",
        "V57 no-AI news and K-line boundaries are present",
        started,
        metadata={"markers": list(STATIC_MARKERS)},
    )


def _run_unittest_check(root: Path, python_exe: str) -> CheckResult:
    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("SEARXNG_PUBLIC_INSTANCES_ENABLED", "false")
    completed = subprocess.run(
        [python_exe, "-m", "unittest", *UNITTEST_MODULES],
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
            "v57_unittests",
            "V57 backend and verifier tests pass",
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
        "v57_unittests",
        "V57 backend and verifier tests pass",
        started,
        metadata={"modules": list(UNITTEST_MODULES), "stderr_tail": completed.stderr[-1000:]},
    )


def _json_get(url: str, timeout_sec: float = 20.0) -> dict:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with urllib.request.urlopen(request, timeout=timeout_sec) as response:
        raw = response.read().decode("utf-8", errors="replace")
        return json.loads(raw)


def _run_live_read_check(live_url: str) -> CheckResult:
    started = time.monotonic()
    base = live_url.rstrip("/")
    try:
        health = _json_get(f"{base}/health", timeout_sec=10)
        snapshot = _json_get(
            f"{base}/api/v1/stocks/{urllib.parse.quote('AAPL', safe='')}/snapshot",
            timeout_sec=30,
        )
        intelligence = snapshot.get("intelligence") or {}
        news_center = intelligence.get("news_center") or intelligence.get("newsCenter") or {}
        kline_forecast = intelligence.get("kline_forecast") or intelligence.get("klineForecast") or {}
        failures: list[str] = []
        if health.get("status") != "ok":
            failures.append("health_not_ok")
        if snapshot.get("ai_used") is not False and snapshot.get("aiUsed") is not False:
            failures.append("snapshot_ai_used_not_false")
        if not news_center:
            failures.append("missing_news_center")
        if news_center.get("ai_used") is not False and news_center.get("aiUsed") is not False:
            failures.append("news_center_ai_used_not_false")
        if news_center.get("public_search_used") is not False and news_center.get("publicSearchUsed") is not False:
            failures.append("news_center_public_search_used_not_false")
        if not kline_forecast:
            failures.append("missing_kline_forecast")
        if kline_forecast.get("kronos_model_used") is not False and kline_forecast.get("kronosModelUsed") is not False:
            failures.append("kline_forecast_kronos_model_used_not_false")
        if "not investment advice" not in str(kline_forecast.get("boundary") or ""):
            failures.append("kline_forecast_boundary_missing")
        if failures:
            return _result(
                "v57_live_read_smoke",
                "Live 8018 AAPL news/K-line no-AI payload is usable",
                started,
                status="failed",
                error="live V57 read smoke failed",
                metadata={"failures": failures, "health": health},
            )
        return _result(
            "v57_live_read_smoke",
            "Live 8018 AAPL news/K-line no-AI payload is usable",
            started,
            metadata={
                "health": health.get("status"),
                "stock_code": snapshot.get("stock_code") or snapshot.get("stockCode"),
                "news_items": len(news_center.get("items") or []),
                "kline_scenarios": len(kline_forecast.get("scenarios") or []),
            },
        )
    except Exception as exc:
        return _result(
            "v57_live_read_smoke",
            "Live 8018 AAPL news/K-line no-AI payload is usable",
            started,
            status="failed",
            error=str(exc),
        )


def run_local_news_kline_v57_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str = sys.executable,
    run_subprocess: bool = True,
    live_url: str | None = None,
) -> list[CheckResult]:
    root = Path(project_root)
    results = [
        _run_required_files_check(root),
        _run_static_boundary_check(root),
    ]
    if run_subprocess:
        results.append(_run_unittest_check(root, python_exe))
    else:
        results.append(
            CheckResult(
                "v57_unittests",
                "V57 backend and verifier tests pass",
                "skipped",
                metadata={"reason": "subprocess disabled"},
            )
        )
    if live_url:
        results.append(_run_live_read_check(live_url))
    else:
        results.append(
            CheckResult(
                "v57_live_read_smoke",
                "Live 8018 AAPL news/K-line no-AI payload is usable",
                "skipped",
                metadata={"reason": "live url not provided"},
            )
        )
    return results


def _print_results(results: Sequence[CheckResult], *, as_json: bool) -> None:
    if as_json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        return
    for result in results:
        status = result.status.upper()
        detail = f" - {result.error}" if result.error else ""
        print(f"[{status}] {result.check_id}: {result.title}{detail}")
        if result.metadata:
            print(json.dumps(result.metadata, ensure_ascii=False, sort_keys=True))


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V57 local news and K-line forecast lab.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--live-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_local_news_kline_v57_checks(
        project_root=Path(args.project_root),
        python_exe=args.python_exe,
        run_subprocess=not args.skip_subprocess,
        live_url=args.live_url,
    )
    _print_results(results, as_json=args.json)
    failed = [result for result in results if result.status == "failed"]
    if failed:
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

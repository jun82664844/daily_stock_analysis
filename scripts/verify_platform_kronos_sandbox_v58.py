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
OK_MARKER = "DSA_PLATFORM_KRONOS_SANDBOX_V58_OK"

REQUIRED_FILES = (
    "src/services/kronos_forecast_service.py",
    "api/v1/endpoints/stocks.py",
    "api/v1/schemas/basic_query.py",
    "api/middlewares/auth.py",
    "tests/test_kronos_forecast_service_v58.py",
    "tests/test_kronos_forecast_api_v58.py",
    "tests/test_platform_kronos_sandbox_v58.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/api/__tests__/stocks.test.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "docs/superpowers/plans/2026-07-06-dsa-v58-kronos-sandbox.md",
)

STATIC_MARKERS = (
    "KronosForecastService",
    "check_availability",
    "KRONOS_ENABLED",
    "KRONOS_MODEL_ID",
    "KRONOS_TOKENIZER_ID",
    "KRONOS_RECORD_PATH",
    "model_unavailable",
    "model_disabled",
    "kronos_model_used",
    "public_search_used",
    "ai_used",
    "kronos-forecast",
    "require_model",
    "basic-query-kronos-run",
    "basic-query-kronos-live-result",
    "basic-query-kronos-dependency-status",
    "basic-query-kronos-backtest-summary",
    "No-go",
    "local-only",
    "not investment advice",
    "Do not commit real API Key",
    OK_MARKER,
)

UNITTEST_MODULES = (
    "tests.test_kronos_forecast_service_v58",
    "tests.test_kronos_forecast_api_v58",
    "tests.test_platform_kronos_sandbox_v58",
)

FRONTEND_TEST_ARGS = (
    "npm",
    "run",
    "test",
    "--",
    "src/api/__tests__/stocks.test.ts",
    "src/pages/__tests__/HomePage.test.tsx",
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
            "v58_required_files_present",
            "V58 Kronos sandbox files exist",
            started,
            status="failed",
            error="required files missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v58_required_files_present",
        "V58 Kronos sandbox files exist",
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
    missing = [marker for marker in STATIC_MARKERS if marker not in combined]
    unsafe = []
    for marker in (
        "sk-live-",
        "stripe_live",
        "BILLING_PROVIDER=stripe",
        "public_search_used\": true",
        "ai_used\": true",
    ):
        marker_lower = marker.lower()
        for line in combined.splitlines():
            line_lower = line.lower()
            if marker_lower not in line_lower:
                continue
            if "assertnotin" in line_lower or "not.tohavetextcontent" in line_lower or "not in" in line_lower:
                continue
            unsafe.append(marker)
            break
    if missing or unsafe:
        return _result(
            "v58_static_kronos_boundaries",
            "V58 Kronos model/fallback boundaries are explicit",
            started,
            status="failed",
            error="static V58 Kronos check failed",
            metadata={"missing_markers": missing, "unsafe_markers": unsafe},
        )
    return _result(
        "v58_static_kronos_boundaries",
        "V58 Kronos model/fallback boundaries are explicit",
        started,
        metadata={"markers": list(STATIC_MARKERS)},
    )


def _run_unittest_check(root: Path, python_exe: str) -> CheckResult:
    started = time.monotonic()
    env = os.environ.copy()
    env.setdefault("KRONOS_ENABLED", "false")
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
            "v58_unittests",
            "V58 backend and verifier tests pass",
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
        "v58_unittests",
        "V58 backend and verifier tests pass",
        started,
        metadata={"modules": list(UNITTEST_MODULES), "stderr_tail": completed.stderr[-1000:]},
    )


def _run_frontend_test_check(root: Path) -> CheckResult:
    started = time.monotonic()
    completed = subprocess.run(
        list(FRONTEND_TEST_ARGS),
        cwd=root / "apps" / "dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
        shell=os.name == "nt",
    )
    if completed.returncode != 0:
        return _result(
            "v58_frontend_tests",
            "V58 frontend Kronos UI tests pass",
            started,
            status="failed",
            error="frontend test command failed",
            metadata={
                "returncode": completed.returncode,
                "stdout_tail": completed.stdout[-2000:],
                "stderr_tail": completed.stderr[-2000:],
                "command": list(FRONTEND_TEST_ARGS),
            },
        )
    return _result(
        "v58_frontend_tests",
        "V58 frontend Kronos UI tests pass",
        started,
        metadata={"stdout_tail": completed.stdout[-1000:]},
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
        forecast = _json_get(
            f"{base}/api/v1/stocks/{urllib.parse.quote('AAPL', safe='')}/kronos-forecast?lookback=20&horizon=5",
            timeout_sec=35,
        )
        failures: list[str] = []
        if health.get("status") != "ok":
            failures.append("health_not_ok")
        if forecast.get("ai_used") is not False and forecast.get("aiUsed") is not False:
            failures.append("forecast_ai_used_not_false")
        if forecast.get("public_search_used") is not False and forecast.get("publicSearchUsed") is not False:
            failures.append("forecast_public_search_used_not_false")
        if forecast.get("kronos_model_used") is True or forecast.get("kronosModelUsed") is True:
            if forecast.get("status") != "model_ready":
                failures.append("model_used_without_model_ready_status")
        if "not investment advice" not in str(forecast.get("boundary") or ""):
            failures.append("boundary_missing")
        if not forecast.get("record_id") and not forecast.get("recordId"):
            failures.append("missing_record_id")
        if not forecast.get("dependency_status") and not forecast.get("dependencyStatus"):
            failures.append("missing_dependency_status")
        if failures:
            return _result(
                "v58_live_kronos_read",
                "Live Kronos sandbox endpoint is explicit and secret-free",
                started,
                status="failed",
                error="live V58 Kronos read failed",
                metadata={"failures": failures, "health": health, "forecast_status": forecast.get("status")},
            )
        return _result(
            "v58_live_kronos_read",
            "Live Kronos sandbox endpoint is explicit and secret-free",
            started,
            metadata={
                "health": health.get("status"),
                "status": forecast.get("status"),
                "source": forecast.get("source"),
                "kronos_model_used": forecast.get("kronos_model_used"),
                "missing_dependencies": forecast.get("missing_dependencies"),
            },
        )
    except Exception as exc:
        return _result(
            "v58_live_kronos_read",
            "Live Kronos sandbox endpoint is explicit and secret-free",
            started,
            status="failed",
            error=str(exc),
        )


def run_kronos_sandbox_v58_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str = sys.executable,
    run_subprocess: bool = True,
    run_frontend: bool = True,
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
        results.append(CheckResult("v58_unittests", "V58 backend and verifier tests pass", "skipped"))
    if run_frontend:
        results.append(_run_frontend_test_check(root))
    else:
        results.append(CheckResult("v58_frontend_tests", "V58 frontend Kronos UI tests pass", "skipped"))
    if live_url:
        results.append(_run_live_read_check(live_url))
    else:
        results.append(CheckResult("v58_live_kronos_read", "Live Kronos sandbox endpoint is explicit and secret-free", "skipped"))
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
    parser = argparse.ArgumentParser(description="Verify DSA V58 local Kronos forecast sandbox.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--skip-frontend", action="store_true")
    parser.add_argument("--live-url", default=None)
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_kronos_sandbox_v58_checks(
        project_root=Path(args.project_root),
        python_exe=args.python_exe,
        run_subprocess=not args.skip_subprocess,
        run_frontend=not args.skip_frontend,
        live_url=args.live_url,
    )
    _print_results(results, as_json=args.json)
    failed = [result for result in results if result.status == "failed"]
    if failed:
        print(f"{OK_MARKER}=FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

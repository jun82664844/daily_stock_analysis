from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_local_v1_operability import _resolve_executable  # noqa: E402
from scripts.verify_platform_local_functional_v5 import (  # noqa: E402
    DEFAULT_BASE_URL,
    _get_json,
    _json_request,
    _new_smoke_credentials,
    _open_json,
    _url_join,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_MARKET_REFRESH_V22_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md",
    "scripts/verify_platform_local_market_refresh_v22.py",
    "tests/test_platform_local_market_refresh_v22.py",
    "src/services/basic_query_service.py",
    "api/v1/endpoints/stocks.py",
    "api/v1/schemas/basic_query.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/api/__tests__/stocks.test.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_market_refresh_v22.py",
)


@dataclass(frozen=True)
class LocalMarketRefreshV22Result:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
            "optional": self.optional,
        }


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict[str, Any] | None = None,
    optional: bool = False,
) -> LocalMarketRefreshV22Result:
    return LocalMarketRefreshV22Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


def _read_text(root: Path, rel_path: str) -> str:
    path = root / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def _get(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def evaluate_market_refresh_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    shape_summary_present = any(key in summary for key in ("service", "endpoint", "frontend"))
    if shape_summary_present:
        service = summary.get("service")
        if not isinstance(service, Mapping):
            problems.append("service:missing")
        else:
            if service.get("accepts_force_refresh") is not True:
                problems.append("service:force_refresh_missing")
            if service.get("bypasses_cache") is not True:
                problems.append("service:does_not_bypass_cache")
            if service.get("ai_used") is not False:
                problems.append("service:ai_used_not_false")
            if _get(service, "refresh_mode") != "force_refresh":
                problems.append("service:refresh_mode_not_force")

        endpoint = summary.get("endpoint")
        if not isinstance(endpoint, Mapping):
            problems.append("endpoint:missing")
        else:
            if endpoint.get("accepts_refresh_query") is not True:
                problems.append("endpoint:refresh_query_missing")
            if endpoint.get("passes_force_refresh") is not True:
                problems.append("endpoint:force_refresh_not_passed")

        frontend = summary.get("frontend")
        if not isinstance(frontend, Mapping):
            problems.append("frontend:missing")
        else:
            if frontend.get("api_uses_refresh_query") is not True:
                problems.append("frontend:api_refresh_query_missing")
            if frontend.get("refresh_button_visible") is not True:
                problems.append("frontend:refresh_button_missing")
            if frontend.get("refresh_diagnostics_visible") is not True:
                problems.append("frontend:refresh_diagnostics_missing")
            if frontend.get("ai_submission_guard") is not True:
                problems.append("frontend:ai_guard_missing")

    live = summary.get("live")
    if isinstance(live, Mapping):
        if live.get("status_code") != 200:
            problems.append("live:status_not_200")
        if live.get("ai_used") is not False:
            problems.append("live:ai_used_not_false")
        if live.get("refresh_mode") != "force_refresh":
            problems.append("live:refresh_mode_not_force")
        if live.get("refresh_requested") is not True:
            problems.append("live:refresh_not_requested")
    return problems


def _run_required_files_check(root: Path) -> LocalMarketRefreshV22Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v22_required_files_present",
            "Local Market Refresh V22 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v22_required_files_present",
        "Local Market Refresh V22 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalMarketRefreshV22Result:
    started = time.monotonic()
    ignored: list[str] = []
    for rel_path in VERIFIER_FILES:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0:
            ignored.append(rel_path)
    if ignored:
        return _result(
            "v22_verifiers_visible_to_git",
            "V22 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v22_verifiers_visible_to_git",
        "V22 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_source_shape_check(root: Path) -> LocalMarketRefreshV22Result:
    started = time.monotonic()
    basic_query = _read_text(root, "src/services/basic_query_service.py")
    stocks_endpoint = _read_text(root, "api/v1/endpoints/stocks.py")
    stocks_api = _read_text(root, "apps/dsa-web/src/api/stocks.ts")
    home_page = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    summary = {
        "service": {
            "accepts_force_refresh": "force_refresh: bool = False" in basic_query,
            "bypasses_cache": "None if force_refresh else self.cache.get" in basic_query,
            "refresh_mode": "force_refresh" if '"mode": "force_refresh" if force_refresh' in basic_query else "missing",
            "ai_used": False if '"ai_used": False' in basic_query else None,
        },
        "endpoint": {
            "accepts_refresh_query": "refresh: bool = Query" in stocks_endpoint,
            "passes_force_refresh": "force_refresh=refresh" in stocks_endpoint,
        },
        "frontend": {
            "api_uses_refresh_query": (
                "?refresh=true" in stocks_api
                or "params.set('refresh', 'true')" in stocks_api
                or 'params.set("refresh", "true")' in stocks_api
            ),
            "refresh_button_visible": "basic-query-refresh-market" in home_page,
            "refresh_diagnostics_visible": "diagnostics.refresh" in home_page and "Refresh:" in home_page,
            "ai_submission_guard": "analysisApi.analyzeAsync).not.toHaveBeenCalled" in _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx"),
        },
    }
    problems = evaluate_market_refresh_summary(summary)
    if problems:
        return _result(
            "v22_source_shape",
            "V22 force-refresh source shape remains wired",
            started,
            status="failed",
            error="source shape does not satisfy V22 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v22_source_shape",
        "V22 force-refresh source shape remains wired",
        started,
        metadata={"summary": summary},
    )


def _run_docs_safety_check(root: Path) -> LocalMarketRefreshV22Result:
    started = time.monotonic()
    plan_path = root / "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md"
    if not plan_path.exists():
        return _result(
            "v22_docs_safety",
            "V22 docs keep local-only and no-advice boundaries",
            started,
            status="failed",
            error="V22 plan document is missing",
        )
    text = plan_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    requirements = {
        "marker": OK_MARKER in text,
        "local_only": "local-only" in lower or "local only" in lower or "本地" in text,
        "no_real_payment": "not real payment" in lower or "真实支付" in text,
        "not_investment_advice": "not investment advice" in lower or "不构成投资建议" in text,
        "no_real_api_key": "do not commit real api key" in lower or "真实 api key" in lower or "真实API Key" in text,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v22_docs_safety",
            "V22 docs keep local-only and no-advice boundaries",
            started,
            status="failed",
            error="V22 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v22_docs_safety",
        "V22 docs keep local-only and no-advice boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> LocalMarketRefreshV22Result:
    started = time.monotonic()
    completed = subprocess.run(
        list(command),
        cwd=cwd,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    metadata = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-2200:],
        "stderr_tail": completed.stderr[-2200:],
    }
    if completed.returncode != 0:
        return _result(check_id, title, started, status="failed", error="subprocess check failed", metadata=metadata)
    return _result(check_id, title, started, metadata=metadata)


def _live_payload_summary(status_code: int, payload: Mapping[str, Any] | Any) -> dict[str, Any]:
    diagnostics = payload.get("diagnostics") if isinstance(payload, Mapping) else {}
    diagnostics = diagnostics if isinstance(diagnostics, Mapping) else {}
    refresh = diagnostics.get("refresh") if isinstance(diagnostics, Mapping) else {}
    refresh = refresh if isinstance(refresh, Mapping) else {}
    cache = diagnostics.get("cache") if isinstance(diagnostics, Mapping) else {}
    cache = cache if isinstance(cache, Mapping) else {}
    route = payload.get("route") if isinstance(payload, Mapping) else {}
    route = route if isinstance(route, Mapping) else {}
    return {
        "status_code": status_code,
        "stock_code": payload.get("stock_code") if isinstance(payload, Mapping) else None,
        "market": payload.get("market") if isinstance(payload, Mapping) else None,
        "lane": route.get("data_source_lane"),
        "ai_used": payload.get("ai_used") if isinstance(payload, Mapping) else None,
        "cache_quote": cache.get("quote"),
        "cache_history": cache.get("history"),
        "refresh_mode": refresh.get("mode"),
        "refresh_requested": refresh.get("requested"),
        "degradation": payload.get("degradation") if isinstance(payload, Mapping) else None,
    }


def _run_optional_live_refresh_check(base_url: str) -> LocalMarketRefreshV22Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v22-refresh")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    metadata: dict[str, Any] = {"smoke_email": email, "cleanup_prefix": "e2e+", "symbol": "AAPL"}
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        if register_status >= 400:
            return _result(
                "optional_live_market_refresh",
                "Optional live force-refresh no-AI snapshot smoke",
                started,
                status="degraded",
                error="platform smoke user registration failed",
                metadata=metadata,
                optional=True,
            )
        status_code, payload = _get_json(opener, _url_join(base_url, "/api/v1/stocks/AAPL/snapshot?refresh=true"), timeout=30)
        live_summary = _live_payload_summary(status_code, payload)
        metadata["live"] = live_summary
        problems = evaluate_market_refresh_summary({"live": live_summary})
        if problems:
            return _result(
                "optional_live_market_refresh",
                "Optional live force-refresh no-AI snapshot smoke",
                started,
                status="degraded",
                error="live refresh snapshot did not satisfy V22 shape",
                metadata={**metadata, "problems": problems},
                optional=True,
            )
        return _result(
            "optional_live_market_refresh",
            "Optional live force-refresh no-AI snapshot smoke",
            started,
            metadata=metadata,
            optional=True,
        )
    except urllib.error.HTTPError as exc:
        return _result(
            "optional_live_market_refresh",
            "Optional live force-refresh no-AI snapshot smoke",
            started,
            status="degraded",
            error=f"HTTP Error {exc.code}: {exc.reason}",
            metadata=metadata,
            optional=True,
        )
    except Exception as exc:
        return _result(
            "optional_live_market_refresh",
            "Optional live force-refresh no-AI snapshot smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )


def run_local_market_refresh_v22_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[LocalMarketRefreshV22Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[LocalMarketRefreshV22Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v22_market_refresh_unittest",
                title="V22 market refresh backend unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_market_refresh_v22"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v22_frontend_market_refresh_tests",
                title="Frontend stock API and HomePage market refresh tests pass",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/api/__tests__/stocks.test.ts",
                    "src/pages/__tests__/HomePage.test.tsx",
                ],
            )
        )
    if run_live:
        results.append(_run_optional_live_refresh_check(base_url))
    return results


def _passed_for_marker(results: Sequence[LocalMarketRefreshV22Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[LocalMarketRefreshV22Result]) -> None:
    for result in results:
        if result.status == "passed":
            marker = "[OK]"
        elif result.status in {"degraded", "skipped", "planned"}:
            marker = "[--]"
        else:
            marker = "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")
    if _passed_for_marker(results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA Local Market Refresh V22 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip optional live 8018 HTTP refresh check")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_market_refresh_v22_checks(
        project_root=args.project_root,
        python_exe=args.python_exe,
        base_url=args.base_url,
        run_subprocess=not args.skip_subprocess,
        run_live=not args.skip_live,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        if _passed_for_marker(results):
            print(OK_MARKER)
    else:
        _print_text_report(results)
    return 0 if _passed_for_marker(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

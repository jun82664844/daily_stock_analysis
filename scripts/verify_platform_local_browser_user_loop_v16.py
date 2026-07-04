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
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_local_v1_operability import _resolve_executable  # noqa: E402
from scripts.verify_platform_local_functional_v5 import (  # noqa: E402
    DEFAULT_BASE_URL,
    _json_request,
    _new_smoke_credentials,
    _open_json,
    _url_join,
)
from scripts.verify_platform_local_user_query_loop_v15 import (  # noqa: E402
    evaluate_user_query_snapshot_payload,
    run_local_user_query_loop_v15_checks,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v16-browser-user-loop.md",
    "scripts/verify_platform_local_browser_user_loop_v16.py",
    "tests/test_platform_local_browser_user_loop_v16.py",
    "apps/dsa-web/e2e/platform-user-e2e.spec.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_browser_user_loop_v16.py",
)

EXPECTED_SYMBOL_LANES = {
    "600519": "a_share_market_data",
    "AAPL": "us_market_data",
    "HK00700": "hk_market_data",
    "BTC-USD": "crypto_market_data",
}


@dataclass(frozen=True)
class LocalBrowserUserLoopV16Result:
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
) -> LocalBrowserUserLoopV16Result:
    return LocalBrowserUserLoopV16Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


def _snake_or_camel(mapping: Mapping[str, Any], snake_key: str, camel_key: str) -> Any:
    if snake_key in mapping:
        return mapping.get(snake_key)
    return mapping.get(camel_key)


def _is_git_worktree(root: Path) -> bool:
    completed = subprocess.run(
        ["git", "rev-parse", "--is-inside-work-tree"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.returncode == 0 and completed.stdout.strip() == "true"


def evaluate_live_browser_smoke_summary(summary: Mapping[str, Mapping[str, Any]]) -> list[str]:
    problems: list[str] = []
    for symbol, expected_lane in EXPECTED_SYMBOL_LANES.items():
        item = summary.get(symbol)
        if not isinstance(item, Mapping):
            problems.append(f"{symbol}:missing")
            continue
        if item.get("status_code") != 200:
            problems.append(f"{symbol}:status_not_200")
        if item.get("lane") != expected_lane:
            problems.append(f"{symbol}:unexpected_lane")
        if item.get("ai_used") is not False:
            problems.append(f"{symbol}:ai_used_not_false")
        if not item.get("freshness"):
            problems.append(f"{symbol}:freshness_missing")
    return problems


def _snapshot_summary_from_payload(status_code: int, payload: dict[str, Any]) -> dict[str, Any]:
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}
    quote = payload.get("quote") if isinstance(payload.get("quote"), dict) else {}
    return {
        "status_code": status_code,
        "lane": _snake_or_camel(route, "data_source_lane", "dataSourceLane") or _snake_or_camel(diagnostics, "route_lane", "routeLane"),
        "ai_used": _snake_or_camel(payload, "ai_used", "aiUsed"),
        "freshness": quote.get("freshness"),
        "market": payload.get("market"),
    }


def _run_required_files_check(root: Path) -> LocalBrowserUserLoopV16Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v16_required_files_present",
            "Local Browser User Loop V16 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v16_required_files_present",
        "Local Browser User Loop V16 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalBrowserUserLoopV16Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v16_verifiers_visible_to_git",
            "V16 verifier files are not gitignored",
            started,
            metadata={"checked_files": [], "git_worktree": False},
        )
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
            "v16_verifiers_visible_to_git",
            "V16 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v16_verifiers_visible_to_git",
        "V16 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_live_smoke_summary_shape_check() -> LocalBrowserUserLoopV16Result:
    started = time.monotonic()
    sample = {
        symbol: {
            "status_code": 200,
            "lane": lane,
            "ai_used": False,
            "freshness": "fresh" if symbol != "BTC-USD" else "stale",
        }
        for symbol, lane in EXPECTED_SYMBOL_LANES.items()
    }
    problems = evaluate_live_browser_smoke_summary(sample)
    if problems:
        return _result(
            "v16_live_smoke_summary_shape",
            "V16 live smoke summary shape validates no-AI market lanes",
            started,
            status="failed",
            error="sample live-smoke summary failed validation",
            metadata={"problems": problems},
        )
    return _result(
        "v16_live_smoke_summary_shape",
        "V16 live smoke summary shape validates no-AI market lanes",
        started,
        metadata={"symbols": sorted(EXPECTED_SYMBOL_LANES)},
    )


def _run_v15_compatibility_gate(root: Path, python_exe: str) -> LocalBrowserUserLoopV16Result:
    started = time.monotonic()
    results = run_local_user_query_loop_v15_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
        run_live=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v15_user_query_loop_compatibility",
            "V15 user-query gate remains compatible with V16",
            started,
            status="failed",
            error="V15 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v15_user_query_loop_compatibility",
        "V15 user-query gate remains compatible with V16",
        started,
        metadata=metadata,
    )


def _run_playwright_v16_check(root: Path) -> LocalBrowserUserLoopV16Result:
    started = time.monotonic()
    env = os.environ.copy()
    env["DSA_PLATFORM_E2E"] = "1"
    completed = subprocess.run(
        [
            _resolve_executable("npm"),
            "run",
            "test:smoke",
            "--",
            "platform-user-e2e.spec.ts",
        ],
        cwd=root / "apps" / "dsa-web",
        env=env,
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
        return _result(
            "v16_playwright_user_browser_loop",
            "Playwright ordinary-user browser loop passes",
            started,
            status="failed",
            error="platform-user-e2e.spec.ts failed",
            metadata=metadata,
        )
    return _result(
        "v16_playwright_user_browser_loop",
        "Playwright ordinary-user browser loop passes",
        started,
        metadata=metadata,
    )


def _run_optional_live_multi_market_smoke(base_url: str) -> LocalBrowserUserLoopV16Result:
    started = time.monotonic()
    smoke_email, smoke_password = _new_smoke_credentials("local-v16-user")
    metadata: dict[str, Any] = {
        "base_url": base_url,
        "smoke_email": smoke_email,
        "cleanup_prefix": "e2e+",
        "symbols": list(EXPECTED_SYMBOL_LANES),
    }
    summary: dict[str, dict[str, Any]] = {}
    payload_problems: dict[str, list[str]] = {}
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": smoke_email, "password": smoke_password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        account_status, account_payload = _open_json(
            opener,
            urllib.request.Request(_url_join(base_url, "/api/v1/platform/account"), headers={"Accept": "application/json"}),
            timeout=15,
        )
        metadata["account_status_code"] = account_status
        metadata["account_email"] = account_payload.get("user", {}).get("email") if isinstance(account_payload, dict) else None
        for symbol in EXPECTED_SYMBOL_LANES:
            status_code, payload = _open_json(
                opener,
                urllib.request.Request(
                    _url_join(base_url, f"/api/v1/stocks/{urllib.parse.quote(symbol, safe='')}/snapshot"),
                    headers={"Accept": "application/json"},
                ),
                timeout=25,
            )
            if isinstance(payload, dict):
                summary[symbol] = _snapshot_summary_from_payload(status_code, payload)
                problems = evaluate_user_query_snapshot_payload(payload)
                if problems:
                    payload_problems[symbol] = problems
            else:
                summary[symbol] = {"status_code": status_code, "lane": None, "ai_used": None, "freshness": None}
                payload_problems[symbol] = ["payload_not_object"]
    except Exception as exc:
        return _result(
            "optional_live_multi_market_user_smoke",
            "Optional live V16 ordinary-user multi-market no-AI smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata={**metadata, "summary": summary, "payload_problems": payload_problems},
            optional=True,
        )

    summary_problems = evaluate_live_browser_smoke_summary(summary)
    if account_status != 200 or summary_problems or payload_problems:
        return _result(
            "optional_live_multi_market_user_smoke",
            "Optional live V16 ordinary-user multi-market no-AI smoke",
            started,
            status="degraded",
            error="live ordinary-user multi-market smoke reported degraded data",
            metadata={
                **metadata,
                "summary": summary,
                "summary_problems": summary_problems,
                "payload_problems": payload_problems,
            },
            optional=True,
        )

    return _result(
        "optional_live_multi_market_user_smoke",
        "Optional live V16 ordinary-user multi-market no-AI smoke",
        started,
        metadata={**metadata, "summary": summary},
        optional=True,
    )


def run_local_browser_user_loop_v16_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[LocalBrowserUserLoopV16Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_live_smoke_summary_shape_check(),
        _run_v15_compatibility_gate(root, py),
    ]
    if run_subprocess:
        results.append(_run_playwright_v16_check(root))
    if run_live:
        results.append(_run_optional_live_multi_market_smoke(base_url))
    return results


def _passed_for_marker(results: Sequence[LocalBrowserUserLoopV16Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[LocalBrowserUserLoopV16Result]) -> None:
    for result in results:
        if result.status == "passed":
            marker = "[OK]"
        elif result.status in {"degraded", "skipped", "planned"}:
            marker = "[--]"
        else:
            marker = "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")
    if _passed_for_marker(results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA Local Browser User Loop V16 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip Playwright subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_browser_user_loop_v16_checks(
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

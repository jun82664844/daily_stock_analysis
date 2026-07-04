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
from typing import Any, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_local_v1_operability import _resolve_executable  # noqa: E402
from scripts.verify_platform_local_functional_v5 import DEFAULT_BASE_URL, _json_request, _new_smoke_credentials, _open_json, _url_join  # noqa: E402
from scripts.verify_platform_local_real_use_loop_v14 import run_local_real_use_loop_v14_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v15-user-query-loop.md",
    "scripts/verify_platform_local_user_query_loop_v15.py",
    "tests/test_platform_local_user_query_loop_v15.py",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_user_query_loop_v15.py",
)

EXPECTED_LANES = {
    "a_share_market_data",
    "us_market_data",
    "hk_market_data",
    "crypto_market_data",
}


@dataclass(frozen=True)
class LocalUserQueryLoopV15Result:
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
) -> LocalUserQueryLoopV15Result:
    return LocalUserQueryLoopV15Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


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


def _snake_or_camel(mapping: dict[str, Any], snake_key: str, camel_key: str) -> Any:
    if snake_key in mapping:
        return mapping.get(snake_key)
    return mapping.get(camel_key)


def evaluate_user_query_snapshot_payload(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    encoded = json.dumps(payload, ensure_ascii=False)
    route = payload.get("route") if isinstance(payload.get("route"), dict) else {}
    quote = payload.get("quote") if isinstance(payload.get("quote"), dict) else {}
    diagnostics = payload.get("diagnostics") if isinstance(payload.get("diagnostics"), dict) else {}

    ai_used = _snake_or_camel(payload, "ai_used", "aiUsed")
    if ai_used is not False:
        problems.append("ai_used_not_false")

    route_lane = _snake_or_camel(route, "data_source_lane", "dataSourceLane") or _snake_or_camel(diagnostics, "route_lane", "routeLane")
    if route_lane not in EXPECTED_LANES:
        problems.append("unexpected_or_missing_market_lane")

    ai_required = _snake_or_camel(route, "ai_required", "aiRequired")
    if ai_required is not False:
        problems.append("route_ai_required_not_false")

    if not quote.get("freshness"):
        problems.append("quote_freshness_missing")

    if "sk-" in encoded or "Bearer " in encoded:
        problems.append("secret_like_text_present")

    return problems


def _run_required_files_check(root: Path) -> LocalUserQueryLoopV15Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v15_required_files_present",
            "Local User Query Loop V15 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v15_required_files_present",
        "Local User Query Loop V15 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalUserQueryLoopV15Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v15_verifiers_visible_to_git",
            "V15 verifier files are not gitignored",
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
            "v15_verifiers_visible_to_git",
            "V15 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v15_verifiers_visible_to_git",
        "V15 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_frontend_v15_test_check(root: Path) -> LocalUserQueryLoopV15Result:
    started = time.monotonic()
    completed = subprocess.run(
        [
            _resolve_executable("npm"),
            "test",
            "--",
            "--run",
            "src/pages/__tests__/HomePage.test.tsx",
            "--testNamePattern",
            "ordinary-user account guardrails",
        ],
        cwd=root / "apps" / "dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    metadata = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1800:],
        "stderr_tail": completed.stderr[-1800:],
    }
    if completed.returncode != 0:
        return _result(
            "v15_frontend_user_query_guardrails",
            "HomePage ordinary-user query guardrails test passes",
            started,
            status="failed",
            error="HomePage V15 target test failed",
            metadata=metadata,
        )
    return _result(
        "v15_frontend_user_query_guardrails",
        "HomePage ordinary-user query guardrails test passes",
        started,
        metadata=metadata,
    )


def _run_v14_compatibility_gate(root: Path, python_exe: str) -> LocalUserQueryLoopV15Result:
    started = time.monotonic()
    results = run_local_real_use_loop_v14_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
        run_live=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v14_real_use_loop_compatibility",
            "V14 real-use gate remains compatible with V15",
            started,
            status="failed",
            error="V14 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v14_real_use_loop_compatibility",
        "V14 real-use gate remains compatible with V15",
        started,
        metadata=metadata,
    )


def _run_payload_shape_check() -> LocalUserQueryLoopV15Result:
    started = time.monotonic()
    samples = [
        {
            "stock_code": "600519",
            "market": "cn",
            "quote": {"freshness": "fresh", "source": "akshare"},
            "route": {"data_source_lane": "a_share_market_data", "ai_required": False},
            "ai_used": False,
        },
        {
            "stockCode": "AAPL",
            "market": "us",
            "quote": {"freshness": "fresh", "source": "yahoo_chart"},
            "route": {"dataSourceLane": "us_market_data", "aiRequired": False},
            "aiUsed": False,
        },
        {
            "stockCode": "HK00700",
            "market": "hk",
            "quote": {"freshness": "fresh", "source": "yahoo_chart"},
            "route": {"dataSourceLane": "hk_market_data", "aiRequired": False},
            "aiUsed": False,
        },
        {
            "stockCode": "BTC-USD",
            "market": "crypto",
            "quote": {"freshness": "stale", "source": "crypto_yahoo_chart"},
            "route": {"dataSourceLane": "crypto_market_data", "aiRequired": False},
            "aiUsed": False,
        },
    ]
    sample_results = {sample["market"]: evaluate_user_query_snapshot_payload(sample) for sample in samples}
    failed = {market: problems for market, problems in sample_results.items() if problems}
    if failed:
        return _result(
            "v15_no_ai_market_lane_payload_shape",
            "No-AI market-lane snapshot payloads are shaped for the user query loop",
            started,
            status="failed",
            error="sample payloads failed V15 snapshot checks",
            metadata={"failed_samples": failed},
        )
    return _result(
        "v15_no_ai_market_lane_payload_shape",
        "No-AI market-lane snapshot payloads are shaped for the user query loop",
        started,
        metadata={"sample_count": len(samples), "lanes": sorted(EXPECTED_LANES)},
    )


def _run_optional_live_no_ai_snapshot_smoke(base_url: str) -> LocalUserQueryLoopV15Result:
    started = time.monotonic()
    smoke_email, smoke_password = _new_smoke_credentials("local-v15-user")
    metadata: dict[str, Any] = {
        "symbols": ["HK00700"],
        "base_url": base_url,
        "smoke_email": smoke_email,
        "cleanup_prefix": "e2e+",
    }
    try:
        opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": smoke_email, "password": smoke_password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        status_code, payload = _open_json(
            opener,
            urllib.request.Request(_url_join(base_url, "/api/v1/stocks/HK00700/snapshot"), headers={"Accept": "application/json"}),
            timeout=20,
        )
        metadata["status_code"] = status_code
        metadata["payload_lane"] = _snake_or_camel(
            payload.get("route", {}) if isinstance(payload, dict) else {},
            "data_source_lane",
            "dataSourceLane",
        )
        metadata["ai_used"] = _snake_or_camel(payload, "ai_used", "aiUsed") if isinstance(payload, dict) else None
    except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        return _result(
            "optional_live_no_ai_snapshot",
            "Optional live V15 no-AI quick snapshot smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    problems = evaluate_user_query_snapshot_payload(payload if isinstance(payload, dict) else {})
    if status_code != 200 or problems:
        return _result(
            "optional_live_no_ai_snapshot",
            "Optional live V15 no-AI quick snapshot smoke",
            started,
            status="degraded",
            error="live snapshot payload is incomplete",
            metadata={**metadata, "problems": problems},
            optional=True,
        )
    return _result(
        "optional_live_no_ai_snapshot",
        "Optional live V15 no-AI quick snapshot smoke",
        started,
        metadata=metadata,
        optional=True,
    )


def run_local_user_query_loop_v15_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[LocalUserQueryLoopV15Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_payload_shape_check(),
        _run_v14_compatibility_gate(root, py),
    ]
    if run_subprocess:
        results.append(_run_frontend_v15_test_check(root))
    if run_live:
        results.append(_run_optional_live_no_ai_snapshot_smoke(base_url))
    return results


def _passed_for_marker(results: Sequence[LocalUserQueryLoopV15Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[LocalUserQueryLoopV15Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA platform Local User Query Loop V15 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip frontend/backend subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_user_query_loop_v15_checks(
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

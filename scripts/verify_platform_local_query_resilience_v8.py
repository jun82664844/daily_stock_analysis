from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_platform_local_functional_v5 import (  # noqa: E402
    DEFAULT_BASE_URL,
    _get_json,
    _json_request,
    _new_smoke_credentials,
    _open_json,
    _url_join,
)
from scripts.verify_platform_local_query_speed_v7 import run_local_query_speed_v7_checks  # noqa: E402
from scripts.verify_platform_local_usability_v6 import (  # noqa: E402
    MARKET_SNAPSHOT_EXPECTATIONS,
    evaluate_market_snapshot_results,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md",
    "scripts/verify_platform_local_query_resilience_v8.py",
    "tests/test_platform_local_query_resilience_v8.py",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_query_resilience_v8.py",
)


@dataclass(frozen=True)
class QueryResilienceV8Result:
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
) -> QueryResilienceV8Result:
    return QueryResilienceV8Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


def _run_required_files_check(root: Path) -> QueryResilienceV8Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v8_required_files_present",
            "Local Query Resilience V8 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v8_required_files_present",
        "Local Query Resilience V8 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
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


def _run_verifiers_visible_check(root: Path) -> QueryResilienceV8Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v8_verifiers_visible_to_git",
            "V8 verifier files are not gitignored",
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
            "v8_verifiers_visible_to_git",
            "V8 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v8_verifiers_visible_to_git",
        "V8 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_v8_unittest_check(root: Path, python_exe: str) -> QueryResilienceV8Result:
    started = time.monotonic()
    completed = subprocess.run(
        [python_exe, "-m", "unittest", "tests.test_platform_local_query_resilience_v8"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    metadata = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1200:],
        "stderr_tail": completed.stderr[-1200:],
    }
    if completed.returncode != 0:
        return _result(
            "v8_backend_unittest",
            "V8 backend query-resilience tests pass",
            started,
            status="failed",
            error="tests.test_platform_local_query_resilience_v8 failed",
            metadata=metadata,
        )
    return _result(
        "v8_backend_unittest",
        "V8 backend query-resilience tests pass",
        started,
        metadata=metadata,
    )


def _run_v7_required_gate(
    *,
    root: Path,
    python_exe: str,
    base_url: str,
    run_subprocess: bool,
    run_live: bool,
) -> QueryResilienceV8Result:
    started = time.monotonic()
    results = run_local_query_speed_v7_checks(
        project_root=root,
        python_exe=python_exe,
        base_url=base_url,
        run_subprocess=run_subprocess,
        run_live=run_live,
    )
    failed = [
        getattr(result, "check_id", "unknown")
        for result in results
        if getattr(result, "status", "failed") == "failed"
    ]
    metadata = {
        "checked_results": len(results),
        "failed_checks": failed,
        "degraded_checks": [
            getattr(result, "check_id", "unknown")
            for result in results
            if getattr(result, "status", "") == "degraded"
        ],
    }
    if failed:
        return _result(
            "v7_query_speed_gate",
            "V7 query speed gate remains compatible with V8",
            started,
            status="failed",
            error="V7 verifier has failed checks",
            metadata=metadata,
        )
    return _result(
        "v7_query_speed_gate",
        "V7 query speed gate remains compatible with V8",
        started,
        metadata=metadata,
    )


def evaluate_snapshot_resilience(results: dict[str, dict[str, Any]]) -> list[str]:
    bad_symbols: list[str] = []
    for symbol, item in sorted(results.items()):
        if item.get("error") or item.get("status_code") != 200:
            continue
        diagnostics = item.get("diagnostics")
        if not isinstance(diagnostics, dict):
            bad_symbols.append(symbol)
            continue
        timeouts = diagnostics.get("timeouts")
        errors = diagnostics.get("errors")
        fallback = diagnostics.get("fallback")
        if not isinstance(timeouts, dict) or not {"quote", "history"}.issubset(timeouts):
            bad_symbols.append(symbol)
            continue
        if not isinstance(errors, dict) or not {"quote", "history"}.issubset(errors):
            bad_symbols.append(symbol)
            continue
        allowed_fallbacks = {"live", "cache", "stale_cache", "disk_cache", "stale_disk_cache", "none"}
        if not isinstance(fallback, dict) or fallback.get("quote") not in allowed_fallbacks:
            bad_symbols.append(symbol)
            continue
        if fallback.get("history") not in allowed_fallbacks:
            bad_symbols.append(symbol)
    return bad_symbols


def _run_optional_live_resilience_check(base_url: str) -> QueryResilienceV8Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v8-query")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    snapshots: dict[str, dict[str, Any]] = {}
    metadata: dict[str, Any] = {"smoke_email": email, "cleanup_prefix": "e2e+", "snapshots": snapshots}
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        if register_status >= 400:
            return _result(
                "optional_live_query_resilience",
                "Optional live no-AI resilience smoke across CN/US/HK/crypto",
                started,
                status="degraded",
                error="platform smoke user registration failed",
                metadata=metadata,
                optional=True,
            )
        login_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/login"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["login_status_code"] = login_status
        if login_status >= 400:
            return _result(
                "optional_live_query_resilience",
                "Optional live no-AI resilience smoke across CN/US/HK/crypto",
                started,
                status="degraded",
                error="platform smoke user login failed",
                metadata=metadata,
                optional=True,
            )
        for symbol in MARKET_SNAPSHOT_EXPECTATIONS:
            try:
                status_code, payload = _get_json(opener, _url_join(base_url, f"/api/v1/stocks/{symbol}/snapshot"), timeout=12)
                route = payload.get("route", {}) if isinstance(payload, dict) else {}
                snapshots[symbol] = {
                    "status_code": status_code,
                    "market": payload.get("market") if isinstance(payload, dict) else None,
                    "ai_used": payload.get("ai_used") if isinstance(payload, dict) else None,
                    "lane": route.get("data_source_lane") if isinstance(route, dict) else None,
                    "diagnostics": payload.get("diagnostics") if isinstance(payload, dict) else None,
                    "warnings": payload.get("warnings") if isinstance(payload, dict) else None,
                }
            except HTTPError as exc:
                snapshots[symbol] = {"status_code": exc.code, "error": f"HTTP {exc.code}: {exc.reason}"}
            except Exception as exc:
                snapshots[symbol] = {"error": str(exc)}
    except Exception as exc:
        return _result(
            "optional_live_query_resilience",
            "Optional live no-AI resilience smoke across CN/US/HK/crypto",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    bad_route_symbols = evaluate_market_snapshot_results(snapshots)
    bad_resilience_symbols = evaluate_snapshot_resilience(snapshots)
    if bad_route_symbols or bad_resilience_symbols:
        return _result(
            "optional_live_query_resilience",
            "Optional live no-AI resilience smoke across CN/US/HK/crypto",
            started,
            status="degraded",
            error="one or more live snapshots lacked correct no-AI route or resilience diagnostics",
            metadata={
                **metadata,
                "bad_route_symbols": bad_route_symbols,
                "bad_resilience_symbols": bad_resilience_symbols,
            },
            optional=True,
        )
    return _result(
        "optional_live_query_resilience",
        "Optional live no-AI resilience smoke across CN/US/HK/crypto",
        started,
        metadata=metadata,
        optional=True,
    )


def run_local_query_resilience_v8_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[QueryResilienceV8Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
    ]
    if run_subprocess:
        results.append(_run_v8_unittest_check(root, py))
        results.append(
            _run_v7_required_gate(
                root=root,
                python_exe=py,
                base_url=base_url,
                run_subprocess=False,
                run_live=run_live,
            )
        )
    if run_live:
        results.append(_run_optional_live_resilience_check(base_url))
    return results


def _passed_for_marker(results: Sequence[QueryResilienceV8Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[QueryResilienceV8Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Query Resilience V8 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip V8 unittest and V7 verifier subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_query_resilience_v8_checks(
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

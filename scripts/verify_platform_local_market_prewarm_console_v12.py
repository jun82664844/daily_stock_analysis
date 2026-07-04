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
from scripts.verify_local_v1_operability import _resolve_executable  # noqa: E402
from scripts.verify_platform_local_market_source_ops_v11 import (  # noqa: E402
    evaluate_market_source_ops_payload,
    run_local_market_source_ops_v11_checks,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK"
DEFAULT_PREWARM_SYMBOLS = ("600519", "AAPL", "HK00700", "BTC-USD")

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-02-dsa-local-v12-market-prewarm-console.md",
    "scripts/verify_platform_local_market_prewarm_console_v12.py",
    "tests/test_platform_local_market_prewarm_console_v12.py",
    "apps/dsa-web/src/pages/AdminPage.tsx",
    "apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx",
    "apps/dsa-web/src/i18n/uiText.ts",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_market_prewarm_console_v12.py",
)


@dataclass(frozen=True)
class MarketPrewarmConsoleV12Result:
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
) -> MarketPrewarmConsoleV12Result:
    return MarketPrewarmConsoleV12Result(
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


def _run_required_files_check(root: Path) -> MarketPrewarmConsoleV12Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v12_required_files_present",
            "Local Market Prewarm Console V12 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v12_required_files_present",
        "Local Market Prewarm Console V12 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> MarketPrewarmConsoleV12Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v12_verifiers_visible_to_git",
            "V12 verifier files are not gitignored",
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
            "v12_verifiers_visible_to_git",
            "V12 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v12_verifiers_visible_to_git",
        "V12 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_frontend_admin_test_check(root: Path) -> MarketPrewarmConsoleV12Result:
    started = time.monotonic()
    completed = subprocess.run(
        [_resolve_executable("npm"), "test", "--", "--run", "src/pages/__tests__/AdminPage.test.tsx"],
        cwd=root / "apps" / "dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    metadata = {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1600:],
        "stderr_tail": completed.stderr[-1600:],
    }
    if completed.returncode != 0:
        return _result(
            "v12_frontend_admin_prewarm_test",
            "AdminPage prewarm console test passes",
            started,
            status="failed",
            error="AdminPage target test failed",
            metadata=metadata,
        )
    return _result(
        "v12_frontend_admin_prewarm_test",
        "AdminPage prewarm console test passes",
        started,
        metadata=metadata,
    )


def _run_v11_required_gate(
    *,
    root: Path,
    python_exe: str,
    base_url: str,
    run_subprocess: bool,
    run_live: bool,
) -> MarketPrewarmConsoleV12Result:
    started = time.monotonic()
    results = run_local_market_source_ops_v11_checks(
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
            "v11_market_source_ops_gate",
            "V11 source-ops gate remains compatible with V12",
            started,
            status="failed",
            error="V11 verifier has failed checks",
            metadata=metadata,
        )
    return _result(
        "v11_market_source_ops_gate",
        "V11 source-ops gate remains compatible with V12",
        started,
        metadata=metadata,
    )


def evaluate_prewarm_console_payload(payload: dict[str, Any], symbols: Sequence[str] = DEFAULT_PREWARM_SYMBOLS) -> list[str]:
    problems: list[str] = []
    if payload.get("ai_used") is not False:
        problems.append("ai_used_not_false")
    if payload.get("requested") != len(symbols):
        problems.append("requested_count_mismatch")
    warmed = payload.get("warmed")
    degraded = payload.get("degraded")
    if not isinstance(warmed, int) or warmed < 0:
        problems.append("warmed_missing")
    if not isinstance(degraded, int) or degraded < 0:
        problems.append("degraded_missing")
    if isinstance(warmed, int) and isinstance(degraded, int) and warmed + degraded > len(symbols):
        problems.append("summary_count_overflow")
    payload_symbols = payload.get("symbols")
    if not isinstance(payload_symbols, list) or set(map(str, symbols)) - {str(item) for item in payload_symbols}:
        problems.append("symbols_incomplete")
    if not isinstance(payload.get("results"), dict):
        problems.append("results_missing")
    if not isinstance(payload.get("elapsed_ms"), (int, float)):
        problems.append("elapsed_ms_missing")
    return problems


def _run_optional_live_prewarm_check(base_url: str) -> MarketPrewarmConsoleV12Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v12-prewarm")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    metadata: dict[str, Any] = {
        "smoke_email": email,
        "cleanup_prefix": "e2e+",
        "symbols": list(DEFAULT_PREWARM_SYMBOLS),
    }
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        if register_status >= 400:
            return _result(
                "optional_live_market_prewarm_console",
                "Optional live V12 market prewarm console smoke",
                started,
                status="degraded",
                error="platform smoke user registration failed",
                metadata=metadata,
                optional=True,
            )
        prewarm_status, prewarm_payload = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/stocks/prewarm"), {"symbols": list(DEFAULT_PREWARM_SYMBOLS)}),
            timeout=60,
        )
        metadata["prewarm_status_code"] = prewarm_status
        metadata["prewarm_payload"] = prewarm_payload
        health_status, health_payload = _get_json(opener, _url_join(base_url, "/api/v1/stocks/sources/health"), timeout=12)
        metadata["health_status_code"] = health_status
        metadata["health_payload"] = health_payload
    except Exception as exc:
        return _result(
            "optional_live_market_prewarm_console",
            "Optional live V12 market prewarm console smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    prewarm_problems = evaluate_prewarm_console_payload(prewarm_payload if isinstance(prewarm_payload, dict) else {})
    health_problems = evaluate_market_source_ops_payload(health_payload if isinstance(health_payload, dict) else {})
    if prewarm_status != 200 or health_status != 200 or prewarm_problems or health_problems:
        return _result(
            "optional_live_market_prewarm_console",
            "Optional live V12 market prewarm console smoke",
            started,
            status="degraded",
            error="live prewarm or source-health payload is incomplete",
            metadata={
                **metadata,
                "prewarm_problems": prewarm_problems,
                "health_problems": health_problems,
            },
            optional=True,
        )
    return _result(
        "optional_live_market_prewarm_console",
        "Optional live V12 market prewarm console smoke",
        started,
        metadata=metadata,
        optional=True,
    )


def run_local_market_prewarm_console_v12_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[MarketPrewarmConsoleV12Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
    ]
    if run_subprocess:
        results.append(_run_frontend_admin_test_check(root))
        results.append(
            _run_v11_required_gate(
                root=root,
                python_exe=py,
                base_url=base_url,
                run_subprocess=False,
                run_live=run_live,
            )
        )
    if run_live:
        results.append(_run_optional_live_prewarm_check(base_url))
    return results


def _passed_for_marker(results: Sequence[MarketPrewarmConsoleV12Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[MarketPrewarmConsoleV12Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Market Prewarm Console V12 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip frontend and V11 subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_market_prewarm_console_v12_checks(
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

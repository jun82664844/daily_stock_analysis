from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Any, Sequence

from dotenv import dotenv_values


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
from scripts.verify_platform_local_market_prewarm_console_v12 import (  # noqa: E402
    DEFAULT_PREWARM_SYMBOLS,
    run_local_market_prewarm_console_v12_checks,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md",
    "scripts/verify_platform_local_market_recovery_console_v13.py",
    "tests/test_platform_local_market_recovery_console_v13.py",
    "src/services/market_source_health.py",
    "src/services/market_source_ops.py",
    "api/v1/endpoints/stocks.py",
    "api/v1/schemas/basic_query.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/pages/AdminPage.tsx",
    "apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_market_recovery_console_v13.py",
)


@dataclass(frozen=True)
class MarketRecoveryConsoleV13Result:
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
) -> MarketRecoveryConsoleV13Result:
    return MarketRecoveryConsoleV13Result(
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


def _run_required_files_check(root: Path) -> MarketRecoveryConsoleV13Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v13_required_files_present",
            "Local Market Recovery Console V13 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v13_required_files_present",
        "Local Market Recovery Console V13 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> MarketRecoveryConsoleV13Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v13_verifiers_visible_to_git",
            "V13 verifier files are not gitignored",
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
            "v13_verifiers_visible_to_git",
            "V13 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v13_verifiers_visible_to_git",
        "V13 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_backend_v13_unittest_check(root: Path, python_exe: str) -> MarketRecoveryConsoleV13Result:
    started = time.monotonic()
    completed = subprocess.run(
        [python_exe, "-m", "unittest", "tests.test_platform_local_market_recovery_console_v13"],
        cwd=root,
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
            "v13_backend_unittest",
            "V13 market recovery backend tests pass",
            started,
            status="failed",
            error="tests.test_platform_local_market_recovery_console_v13 failed",
            metadata=metadata,
        )
    return _result("v13_backend_unittest", "V13 market recovery backend tests pass", started, metadata=metadata)


def _run_frontend_admin_test_check(root: Path) -> MarketRecoveryConsoleV13Result:
    started = time.monotonic()
    completed = subprocess.run(
        [_resolve_executable("npm"), "test", "--", "--run", "src/api/__tests__/stocks.test.ts", "src/pages/__tests__/AdminPage.test.tsx"],
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
            "v13_frontend_admin_recovery_test",
            "AdminPage market recovery console test passes",
            started,
            status="failed",
            error="AdminPage recovery target test failed",
            metadata=metadata,
        )
    return _result("v13_frontend_admin_recovery_test", "AdminPage market recovery console test passes", started, metadata=metadata)


def _run_v12_required_gate(
    *,
    root: Path,
    python_exe: str,
    base_url: str,
    run_subprocess: bool,
    run_live: bool,
) -> MarketRecoveryConsoleV13Result:
    started = time.monotonic()
    results = run_local_market_prewarm_console_v12_checks(
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
            "v12_market_prewarm_gate",
            "V12 prewarm console gate remains compatible with V13",
            started,
            status="failed",
            error="V12 verifier has failed checks",
            metadata=metadata,
        )
    return _result("v12_market_prewarm_gate", "V12 prewarm console gate remains compatible with V13", started, metadata=metadata)


def evaluate_market_recovery_payload(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    if payload.get("ai_used") is not False:
        problems.append("ai_used_not_false")
    if payload.get("mode") != "local_only":
        problems.append("mode_not_local_only")
    if not isinstance(payload.get("reset_sources"), list):
        problems.append("reset_sources_missing")
    if not isinstance(payload.get("reset_count"), int):
        problems.append("reset_count_missing")
    prewarm = payload.get("prewarm")
    if not isinstance(prewarm, dict):
        problems.append("prewarm_missing")
    elif prewarm.get("ai_used") is not False:
        problems.append("prewarm_ai_used_not_false")
    health = payload.get("health")
    if not isinstance(health, dict) or health.get("ai_used") is not False:
        problems.append("health_missing_or_ai_used")
    return problems


def _json_request_with_headers(url: str, payload: dict[str, Any], headers: dict[str, str] | None = None) -> urllib.request.Request:
    request_headers = {"Content-Type": "application/json", "Accept": "application/json"}
    request_headers.update(headers or {})
    return urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers=request_headers,
        method="POST",
    )


def _resolve_live_admin_password(root: Path) -> tuple[str, str]:
    for key in ("DSA_LIVE_ADMIN_PASSWORD", "ADMIN_PASSWORD"):
        value = os.getenv(key)
        if value:
            return value, f"env:{key}"
    try:
        env_values = dotenv_values(root / ".env")
    except Exception:
        env_values = {}
    for key in ("DSA_LIVE_ADMIN_PASSWORD", "ADMIN_PASSWORD"):
        value = env_values.get(key)
        if value:
            return str(value), f"dotenv:{key}"
    return "AdminPass123", "default"


def _run_optional_live_recovery_check(base_url: str) -> MarketRecoveryConsoleV13Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v13-recovery")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    metadata: dict[str, Any] = {"smoke_email": email, "cleanup_prefix": "e2e+"}
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        try:
            ordinary_status, ordinary_payload = _open_json(
                opener,
                _json_request(_url_join(base_url, "/api/v1/stocks/sources/recovery"), {"sources": ["hk_realtime"], "prewarm": False}),
                timeout=15,
            )
        except urllib.error.HTTPError as exc:
            ordinary_status = exc.code
            try:
                ordinary_payload = json.loads(exc.read().decode("utf-8"))
            except Exception:
                ordinary_payload = {"error": str(exc)}
        metadata["ordinary_status_code"] = ordinary_status
        metadata["ordinary_payload"] = ordinary_payload
        if ordinary_status != 403:
            return _result(
                "optional_live_market_recovery_console",
                "Optional live V13 market recovery console smoke",
                started,
                status="degraded",
                error="ordinary user recovery request was not rejected with 403",
                metadata=metadata,
                optional=True,
            )

        admin_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        admin_password, admin_password_source = _resolve_live_admin_password(REPO_ROOT)
        metadata["admin_password_source"] = admin_password_source
        admin_status, _ = _open_json(
            admin_opener,
            _json_request(_url_join(base_url, "/api/v1/auth/login"), {"password": admin_password, "passwordConfirm": admin_password}),
            timeout=15,
        )
        metadata["admin_status_code"] = admin_status
        csrf_token = None
        for cookie in getattr(admin_opener, "handlers", []):
            cookiejar = getattr(cookie, "cookiejar", None)
            if cookiejar is None:
                continue
            for item in cookiejar:
                if item.name == "dsa_csrf_token":
                    csrf_token = item.value
        headers = {"X-DSA-CSRF": csrf_token} if csrf_token else {}
        recovery_status, recovery_payload = _open_json(
            admin_opener,
            _json_request_with_headers(
                _url_join(base_url, "/api/v1/stocks/sources/recovery"),
                {"market": "all", "symbols": list(DEFAULT_PREWARM_SYMBOLS), "prewarm": True},
                headers=headers,
            ),
            timeout=60,
        )
        metadata["recovery_status_code"] = recovery_status
        metadata["recovery_payload"] = recovery_payload
    except Exception as exc:
        return _result(
            "optional_live_market_recovery_console",
            "Optional live V13 market recovery console smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    problems = evaluate_market_recovery_payload(recovery_payload if isinstance(recovery_payload, dict) else {})
    if recovery_status != 200 or problems:
        return _result(
            "optional_live_market_recovery_console",
            "Optional live V13 market recovery console smoke",
            started,
            status="degraded",
            error="live recovery payload is incomplete",
            metadata={**metadata, "problems": problems},
            optional=True,
        )
    return _result("optional_live_market_recovery_console", "Optional live V13 market recovery console smoke", started, metadata=metadata, optional=True)


def run_local_market_recovery_console_v13_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[MarketRecoveryConsoleV13Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
    ]
    if run_subprocess:
        results.append(_run_backend_v13_unittest_check(root, py))
        results.append(_run_frontend_admin_test_check(root))
        results.append(
            _run_v12_required_gate(
                root=root,
                python_exe=py,
                base_url=base_url,
                run_subprocess=False,
                run_live=run_live,
            )
        )
    if run_live:
        results.append(_run_optional_live_recovery_check(base_url))
    return results


def _passed_for_marker(results: Sequence[MarketRecoveryConsoleV13Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[MarketRecoveryConsoleV13Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Market Recovery Console V13 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip frontend/backend and V12 subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_market_recovery_console_v13_checks(
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

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
from scripts.verify_platform_local_functional_v5 import (  # noqa: E402
    DEFAULT_BASE_URL,
    _json_request,
    _new_smoke_credentials,
    _open_json,
    _url_join,
)
from scripts.verify_platform_local_market_recovery_console_v13 import (  # noqa: E402
    run_local_market_recovery_console_v13_checks,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v14-real-use-loop.md",
    "scripts/verify_platform_local_real_use_loop_v14.py",
    "tests/test_platform_local_real_use_loop_v14.py",
    "src/services/local_functional_status.py",
    "api/v1/endpoints/platform.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/api/__tests__/platform.test.ts",
    "apps/dsa-web/src/pages/AdminPage.tsx",
    "apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_real_use_loop_v14.py",
)


@dataclass(frozen=True)
class LocalRealUseLoopV14Result:
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
) -> LocalRealUseLoopV14Result:
    return LocalRealUseLoopV14Result(
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


def _run_required_files_check(root: Path) -> LocalRealUseLoopV14Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v14_required_files_present",
            "Local Real Use Loop V14 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v14_required_files_present",
        "Local Real Use Loop V14 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalRealUseLoopV14Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v14_verifiers_visible_to_git",
            "V14 verifier files are not gitignored",
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
            "v14_verifiers_visible_to_git",
            "V14 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v14_verifiers_visible_to_git",
        "V14 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_backend_v14_unittest_check(root: Path, python_exe: str) -> LocalRealUseLoopV14Result:
    started = time.monotonic()
    completed = subprocess.run(
        [python_exe, "-m", "unittest", "tests.test_platform_local_real_use_loop_v14"],
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
            "v14_backend_unittest",
            "V14 local real-use backend tests pass",
            started,
            status="failed",
            error="tests.test_platform_local_real_use_loop_v14 failed",
            metadata=metadata,
        )
    return _result("v14_backend_unittest", "V14 local real-use backend tests pass", started, metadata=metadata)


def _run_frontend_v14_test_check(root: Path) -> LocalRealUseLoopV14Result:
    started = time.monotonic()
    completed = subprocess.run(
        [
            _resolve_executable("npm"),
            "test",
            "--",
            "--run",
            "src/api/__tests__/platform.test.ts",
            "src/pages/__tests__/AdminPage.test.tsx",
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
            "v14_frontend_admin_status_test",
            "AdminPage local functional status tests pass",
            started,
            status="failed",
            error="AdminPage local functional status target test failed",
            metadata=metadata,
        )
    return _result("v14_frontend_admin_status_test", "AdminPage local functional status tests pass", started, metadata=metadata)


def _run_v13_required_gate(root: Path, python_exe: str) -> LocalRealUseLoopV14Result:
    started = time.monotonic()
    results = run_local_market_recovery_console_v13_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
        run_live=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v13_recovery_gate_compatibility",
            "V13 market recovery gate remains compatible with V14",
            started,
            status="failed",
            error="V13 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v13_recovery_gate_compatibility",
        "V13 market recovery gate remains compatible with V14",
        started,
        metadata=metadata,
    )


def evaluate_local_status_payload(payload: dict[str, Any]) -> list[str]:
    problems: list[str] = []
    encoded = json.dumps(payload, ensure_ascii=False)
    if payload.get("mode") != "local_only":
        problems.append("mode_not_local_only")
    if payload.get("ai_used") is not False:
        problems.append("ai_used_not_false")
    if not isinstance(payload.get("service"), dict) or not payload["service"].get("port"):
        problems.append("service_status_missing")
    if not isinstance(payload.get("market"), dict) or "summary" not in payload["market"]:
        problems.append("market_summary_missing")
    safety = payload.get("safety")
    if not isinstance(safety, dict) or safety.get("no_ai_status") is not True:
        problems.append("safety_no_ai_missing")
    if isinstance(safety, dict) and safety.get("real_payment_enabled") is not False:
        problems.append("real_payment_not_false")
    if "sk-" in encoded or "Bearer " in encoded:
        problems.append("secret_like_text_present")
    return problems


def _read_error_json(exc: urllib.error.HTTPError) -> dict[str, Any]:
    try:
        return json.loads(exc.read().decode("utf-8"))
    except Exception:
        return {"error": str(exc)}


def _open_json_allow_http_error(opener: urllib.request.OpenerDirector, request: urllib.request.Request, timeout: int) -> tuple[int, Any]:
    try:
        return _open_json(opener, request, timeout=timeout)
    except urllib.error.HTTPError as exc:
        return exc.code, _read_error_json(exc)


def _run_optional_live_local_status_check(base_url: str) -> LocalRealUseLoopV14Result:
    started = time.monotonic()
    ordinary_email, ordinary_password = _new_smoke_credentials("local-v14-user")
    admin_email, admin_password = _new_smoke_credentials("local-v14-admin")
    metadata: dict[str, Any] = {
        "ordinary_email": ordinary_email,
        "admin_email": admin_email,
        "cleanup_prefix": "e2e+",
    }
    try:
        from src.config import setup_env
        from src.platform_accounts import PlatformAccountService

        setup_env(override=True)
        PlatformAccountService().create_user(admin_email, admin_password, role="admin", plan="enterprise")

        ordinary_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        register_status, _ = _open_json(
            ordinary_opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": ordinary_email, "password": ordinary_password}),
            timeout=15,
        )
        metadata["ordinary_register_status_code"] = register_status
        ordinary_status, ordinary_payload = _open_json_allow_http_error(
            ordinary_opener,
            urllib.request.Request(_url_join(base_url, "/api/v1/platform/admin/local-status"), headers={"Accept": "application/json"}),
            timeout=15,
        )
        metadata["ordinary_status_code"] = ordinary_status
        metadata["ordinary_payload"] = ordinary_payload
        if ordinary_status != 403:
            return _result(
                "optional_live_local_status",
                "Optional live V14 local status smoke",
                started,
                status="degraded",
                error="ordinary user local-status request was not rejected with 403",
                metadata=metadata,
                optional=True,
            )

        admin_opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
        login_status, _ = _open_json(
            admin_opener,
            _json_request(_url_join(base_url, "/api/v1/platform/login"), {"email": admin_email, "password": admin_password}),
            timeout=15,
        )
        metadata["admin_login_status_code"] = login_status
        status_code, payload = _open_json(
            admin_opener,
            urllib.request.Request(_url_join(base_url, "/api/v1/platform/admin/local-status"), headers={"Accept": "application/json"}),
            timeout=15,
        )
        metadata["admin_status_code"] = status_code
        metadata["payload"] = payload
    except Exception as exc:
        return _result(
            "optional_live_local_status",
            "Optional live V14 local status smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    problems = evaluate_local_status_payload(payload if isinstance(payload, dict) else {})
    if status_code != 200 or problems:
        return _result(
            "optional_live_local_status",
            "Optional live V14 local status smoke",
            started,
            status="degraded",
            error="live local-status payload is incomplete",
            metadata={**metadata, "problems": problems},
            optional=True,
        )
    return _result("optional_live_local_status", "Optional live V14 local status smoke", started, metadata=metadata, optional=True)


def run_local_real_use_loop_v14_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[LocalRealUseLoopV14Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
    ]
    if run_subprocess:
        results.append(_run_backend_v14_unittest_check(root, py))
        results.append(_run_frontend_v14_test_check(root))
        results.append(_run_v13_required_gate(root, py))
    if run_live:
        results.append(_run_optional_live_local_status_check(base_url))
    return results


def _passed_for_marker(results: Sequence[LocalRealUseLoopV14Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[LocalRealUseLoopV14Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Real Use Loop V14 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip frontend/backend subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_real_use_loop_v14_checks(
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

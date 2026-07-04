from __future__ import annotations

import argparse
import json
import secrets
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Sequence
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BASE_URL = "http://127.0.0.1:8018"
OK_MARKER = "DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK"

REQUIRED_FILES = (
    "docs/superpowers/platform-local-v1-acceptance-status.md",
    "docs/superpowers/platform-review-slices.md",
    "docs/superpowers/platform-release-candidate-manifest.md",
    "docs/superpowers/platform-product-rules.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
    "scripts/verify_platform_local_functional_v5.py",
    "scripts/verify_local_v1_operability.py",
    "scripts/verify_platform_query_quality_v4.py",
    "scripts/verify_platform_user_e2e.py",
    "scripts/verify_platform_billing_lifecycle.py",
    "scripts/verify_platform_release_candidate_package.py",
    "tests/test_platform_local_functional_v5.py",
    "tests/test_platform_query_quality_v4.py",
    "tests/test_platform_user_journey.py",
    "tests/test_billing_sandbox_flow.py",
    "tests/test_billing_subscription_lifecycle.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/AccountPage.tsx",
    "apps/dsa-web/src/pages/AdminPage.tsx",
    "apps/dsa-web/src/components/layout/SidebarNav.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_local_v1_operability.py",
    "scripts/verify_platform_query_quality_v4.py",
    "scripts/verify_platform_user_e2e.py",
    "scripts/verify_platform_billing_lifecycle.py",
    "scripts/verify_platform_release_candidate_package.py",
    "scripts/verify_platform_local_functional_v5.py",
)

DOC_FILES = (
    "docs/superpowers/platform-local-v1-acceptance-status.md",
    "docs/superpowers/platform-review-slices.md",
    "docs/superpowers/platform-release-candidate-manifest.md",
    "docs/superpowers/platform-product-rules.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
)

UNITTEST_MODULES = (
    "tests.test_platform_local_functional_v5",
    "tests.test_platform_query_quality_v4",
    "tests.test_platform_user_journey",
    "tests.test_billing_sandbox_flow",
    "tests.test_billing_subscription_lifecycle",
)

EXISTING_VERIFIERS = (
    ("query_quality_v4", "scripts/verify_platform_query_quality_v4.py", "DSA_PLATFORM_QUERY_QUALITY_V4_OK"),
    ("user_e2e", "scripts/verify_platform_user_e2e.py", "DSA_PLATFORM_USER_E2E_V1_OK"),
    ("billing_lifecycle", "scripts/verify_platform_billing_lifecycle.py", "DSA_PLATFORM_BILLING_LIFECYCLE_V1_OK"),
    ("release_candidate_package", "scripts/verify_platform_release_candidate_package.py", None),
)


@dataclass(frozen=True)
class FunctionalV5Result:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)
    optional: bool = False

    def to_dict(self) -> dict:
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
    metadata: dict | None = None,
    optional: bool = False,
) -> FunctionalV5Result:
    return FunctionalV5Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


def _url_join(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _json_request(url: str, payload: dict, *, method: str = "POST") -> urllib.request.Request:
    return urllib.request.Request(
        url,
        data=json.dumps(payload, separators=(",", ":")).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method=method,
    )


def _get_json(opener: urllib.request.OpenerDirector, url: str, *, timeout: int = 10) -> tuple[int, dict | list | str]:
    request = urllib.request.Request(url, headers={"Accept": "application/json"})
    with opener.open(request, timeout=timeout) as response:
        status_code = int(getattr(response, "status", response.getcode()))
        body = response.read(16384).decode("utf-8", errors="replace")
    try:
        return status_code, json.loads(body)
    except json.JSONDecodeError:
        return status_code, body


def _open_json(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    *,
    timeout: int = 10,
) -> tuple[int, dict | list | str]:
    with opener.open(request, timeout=timeout) as response:
        status_code = int(getattr(response, "status", response.getcode()))
        body = response.read(16384).decode("utf-8", errors="replace")
    try:
        return status_code, json.loads(body)
    except json.JSONDecodeError:
        return status_code, body


def _run_required_files_check(root: Path) -> FunctionalV5Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "Local Functional V5 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "Local Functional V5 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> FunctionalV5Result:
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
            "verifiers_visible_to_git",
            "Critical local verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "verifiers_visible_to_git",
        "Critical local verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_docs_safety_check(root: Path) -> FunctionalV5Result:
    started = time.monotonic()
    missing_docs = [rel_path for rel_path in DOC_FILES if not (root / rel_path).exists()]
    combined = "\n".join(_read_text(root / rel_path) for rel_path in DOC_FILES if (root / rel_path).exists())
    lower = combined.lower()
    requirements = {
        OK_MARKER: OK_MARKER in combined,
        "No-go": "no-go" in lower or "不可上线" in combined,
        "sandbox": "sandbox" in lower,
        "not real payment": "not real payment" in lower or "不代表真实支付" in combined,
        "not investment advice": "not investment advice" in lower or "不构成投资建议" in combined,
        "Do not commit real API Key": "do not commit real api key" in lower or "不得提交真实 api key" in lower,
    }
    missing_requirements = sorted(label for label, present in requirements.items() if not present)
    if missing_docs or missing_requirements:
        return _result(
            "docs_keep_v5_safety_copy",
            "Docs keep V5 marker and local-only safety copy",
            started,
            status="failed",
            error="V5 docs are missing required safety copy",
            metadata={"missing_docs": missing_docs, "missing_requirements": missing_requirements},
        )
    return _result(
        "docs_keep_v5_safety_copy",
        "Docs keep V5 marker and local-only safety copy",
        started,
        metadata={"checked_docs": list(DOC_FILES), "requirements": sorted(requirements)},
    )


def _run_command(
    *,
    check_id: str,
    title: str,
    command: Sequence[str],
    root: Path,
    timeout_sec: int = 180,
    required_marker: str | None = None,
) -> FunctionalV5Result:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            list(command),
            cwd=root,
            timeout=timeout_sec,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception as exc:
        return _result(check_id, title, started, status="failed", error=str(exc), metadata={"command": list(command)})

    output = "\n".join(part for part in (completed.stdout, completed.stderr) if part)
    marker_missing = bool(required_marker and required_marker not in output)
    if completed.returncode != 0 or marker_missing:
        return _result(
            check_id,
            title,
            started,
            status="failed",
            error="command failed" if completed.returncode != 0 else "required marker missing",
            metadata={
                "command": list(command),
                "returncode": completed.returncode,
                "required_marker": required_marker,
                "output_tail": output[-4000:],
            },
        )
    return _result(
        check_id,
        title,
        started,
        metadata={"command": list(command), "returncode": completed.returncode, "required_marker": required_marker},
    )


def _run_backend_unittests_check(root: Path, *, python_exe: str) -> FunctionalV5Result:
    return _run_command(
        check_id="backend_functional_v5_unittests",
        title="Backend local functional V5 unit tests pass",
        command=[python_exe, "-m", "unittest", *UNITTEST_MODULES],
        root=root,
        timeout_sec=240,
    )


def _run_existing_verifier_checks(root: Path, *, python_exe: str) -> list[FunctionalV5Result]:
    results: list[FunctionalV5Result] = []
    for verifier_id, rel_path, marker in EXISTING_VERIFIERS:
        results.append(
            _run_command(
                check_id=f"existing_{verifier_id}",
                title=f"Existing verifier passes: {verifier_id}",
                command=[python_exe, rel_path],
                root=root,
                timeout_sec=300,
                required_marker=marker,
            )
        )
    return results


def _run_live_health_check(base_url: str) -> FunctionalV5Result:
    started = time.monotonic()
    opener = urllib.request.build_opener()
    try:
        status_code, payload = _get_json(opener, _url_join(base_url, "/health"), timeout=10)
    except Exception as exc:
        return _result("live_health", "Local 8018 health check responds", started, status="failed", error=str(exc))

    ok = status_code == 200 and isinstance(payload, dict) and payload.get("status") == "ok"
    return _result(
        "live_health",
        "Local 8018 health check responds",
        started,
        status="passed" if ok else "failed",
        error="" if ok else "health endpoint did not return status ok",
        metadata={"status_code": status_code, "payload_keys": sorted(payload) if isinstance(payload, dict) else []},
    )


def _run_live_page_shell_check(base_url: str) -> FunctionalV5Result:
    started = time.monotonic()
    checked: dict[str, int] = {}
    try:
        for path in ("/", "/account", "/admin"):
            request = urllib.request.Request(_url_join(base_url, path), headers={"Accept": "text/html"})
            with urllib.request.urlopen(request, timeout=10) as response:
                status_code = int(getattr(response, "status", response.getcode()))
                body = response.read(16384).decode("utf-8", errors="replace")
            checked[path] = status_code
            if status_code >= 400 or "<html" not in body.lower():
                return _result(
                    "live_page_shell",
                    "Local frontend shell routes respond",
                    started,
                    status="failed",
                    error=f"frontend shell route failed: {path}",
                    metadata={"checked_routes": checked},
                )
    except Exception as exc:
        return _result("live_page_shell", "Local frontend shell routes respond", started, status="failed", error=str(exc), metadata={"checked_routes": checked})
    return _result(
        "live_page_shell",
        "Local frontend shell routes respond",
        started,
        metadata={"checked_routes": checked},
    )


def _new_smoke_credentials(prefix: str) -> tuple[str, str]:
    timestamp = int(time.time())
    nonce = secrets.token_hex(4)
    email = f"e2e+{prefix}-{timestamp}-{nonce}@example.com"
    password = f"{prefix}-{secrets.token_urlsafe(18)}"
    return email, password


def _run_live_platform_smoke_check(base_url: str) -> FunctionalV5Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v5")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    metadata: dict = {"smoke_email": email, "cleanup_prefix": "e2e+", "steps": []}
    try:
        register_status, register_payload = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["steps"].append({"step": "register", "status_code": register_status})
        if register_status >= 400:
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="register failed", metadata=metadata)
        if password in str(register_payload):
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="password leaked in register response", metadata=metadata)

        login_status, login_payload = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/login"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["steps"].append({"step": "login", "status_code": login_status})
        if login_status >= 400:
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="login failed", metadata=metadata)
        if password in str(login_payload):
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="password leaked in login response", metadata=metadata)

        try:
            account_status, account_payload = _get_json(opener, _url_join(base_url, "/api/v1/platform/account"), timeout=15)
        except HTTPError as exc:
            metadata["steps"].append({"step": "account", "status_code": exc.code})
            if exc.code == 404:
                return _result(
                    "live_platform_smoke",
                    "Local platform user register/login smoke",
                    started,
                    status="degraded",
                    error="live 8018 service has register/login but not the current account route; deterministic TestClient coverage is required",
                    metadata=metadata,
                )
            return _result(
                "live_platform_smoke",
                "Local platform user register/login smoke",
                started,
                status="failed",
                error=f"account check returned HTTP {exc.code}",
                metadata=metadata,
            )
        metadata["steps"].append({"step": "account", "status_code": account_status})
        if account_status != 200 or not isinstance(account_payload, dict):
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="account check failed", metadata=metadata)
        if account_payload.get("user", {}).get("email") != email:
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="account user mismatch", metadata=metadata)

        try:
            _get_json(opener, _url_join(base_url, "/api/v1/platform/admin/users"), timeout=15)
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="ordinary user accessed admin users", metadata=metadata)
        except HTTPError as exc:
            metadata["steps"].append({"step": "admin_boundary", "status_code": exc.code})
            if exc.code != 403:
                return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error=f"admin boundary returned HTTP {exc.code}", metadata=metadata)

        try:
            billing_status, billing_payload = _get_json(opener, _url_join(base_url, "/api/v1/billing/account"), timeout=15)
        except HTTPError as exc:
            metadata["steps"].append({"step": "billing_account", "status_code": exc.code})
            if exc.code == 404:
                return _result(
                    "live_platform_smoke",
                    "Local platform user register/login smoke",
                    started,
                    status="degraded",
                    error="live 8018 service has no current billing account route; deterministic TestClient billing coverage is required",
                    metadata=metadata,
                )
            return _result(
                "live_platform_smoke",
                "Local platform user register/login smoke",
                started,
                status="failed",
                error=f"billing summary returned HTTP {exc.code}",
                metadata=metadata,
            )
        metadata["steps"].append({"step": "billing_account", "status_code": billing_status})
        if billing_status != 200 or "sandbox" not in str(billing_payload).lower():
            return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error="billing summary missing local sandbox boundary", metadata=metadata)
    except HTTPError as exc:
        metadata["steps"].append({"step": "http_error", "status_code": exc.code})
        return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error=f"HTTP Error {exc.code}: {exc.reason}", metadata=metadata)
    except Exception as exc:
        return _result("live_platform_smoke", "Local platform user register/login smoke", started, status="failed", error=str(exc), metadata=metadata)

    return _result(
        "live_platform_smoke",
        "Local platform user register/login smoke",
        started,
        metadata=metadata,
    )


def _run_optional_live_snapshot_check(base_url: str) -> FunctionalV5Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v5-snapshot")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    metadata: dict = {"smoke_email": email, "cleanup_prefix": "e2e+", "symbol": "AAPL"}
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        if register_status >= 400:
            return _result(
                "optional_live_snapshot",
                "Optional live no-AI snapshot smoke",
                started,
                status="degraded",
                error="platform smoke user registration failed",
                metadata=metadata,
                optional=True,
            )
        status_code, payload = _get_json(opener, _url_join(base_url, "/api/v1/stocks/AAPL/snapshot"), timeout=30)
        metadata["snapshot_status_code"] = status_code
        metadata["snapshot_market"] = payload.get("market") if isinstance(payload, dict) else None
        metadata["degradation"] = payload.get("degradation") if isinstance(payload, dict) else None
        if status_code == 200 and isinstance(payload, dict) and payload.get("ai_used") is False:
            return _result(
                "optional_live_snapshot",
                "Optional live no-AI snapshot smoke",
                started,
                metadata=metadata,
                optional=True,
            )
        return _result(
            "optional_live_snapshot",
            "Optional live no-AI snapshot smoke",
            started,
            status="degraded",
            error="live snapshot did not return a deterministic no-AI payload",
            metadata=metadata,
            optional=True,
        )
    except Exception as exc:
        return _result(
            "optional_live_snapshot",
            "Optional live no-AI snapshot smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )


def run_local_functional_v5_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
    include_optional_live: bool = True,
) -> list[FunctionalV5Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(_run_backend_unittests_check(root, python_exe=py))
        results.extend(_run_existing_verifier_checks(root, python_exe=py))
    if run_live:
        results.append(_run_live_health_check(base_url))
        results.append(_run_live_page_shell_check(base_url))
        results.append(_run_live_platform_smoke_check(base_url))
        if include_optional_live:
            results.append(_run_optional_live_snapshot_check(base_url))
    return results


def _print_text_report(results: Sequence[FunctionalV5Result]) -> None:
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
    if all(result.status != "failed" for result in results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Functional V5 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip unittest and existing verifier subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--skip-optional-live", action="store_true", help="Skip optional live market snapshot smoke")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_functional_v5_checks(
        project_root=args.project_root,
        python_exe=args.python_exe,
        base_url=args.base_url,
        run_subprocess=not args.skip_subprocess,
        run_live=not args.skip_live,
        include_optional_live=not args.skip_optional_live,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        if all(result.status != "failed" for result in results):
            print(OK_MARKER)
    else:
        _print_text_report(results)
    return 0 if all(result.status != "failed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

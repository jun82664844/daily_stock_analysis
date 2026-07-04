from __future__ import annotations

import argparse
import json
import os
import secrets
import shutil
import subprocess
import sys
import time
import urllib.request
from dataclasses import dataclass, field
from http.cookiejar import CookieJar
from pathlib import Path
from typing import Iterable, Sequence
from urllib.error import HTTPError
from urllib.request import urlopen


DEFAULT_WEB_BASE_URL = "http://127.0.0.1:8018"


@dataclass(frozen=True)
class OperabilityCheck:
    id: str
    title: str
    category: str
    command: list[str] | None = None
    cwd: str | None = None
    url: str | None = None
    optional: bool = False
    timeout_sec: int = 120
    evidence: str = ""

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "title": self.title,
            "category": self.category,
            "command": self.command,
            "cwd": self.cwd,
            "url": self.url,
            "optional": self.optional,
            "timeout_sec": self.timeout_sec,
            "evidence": self.evidence,
        }


@dataclass(frozen=True)
class OperabilityResult:
    check: OperabilityCheck
    status: str
    elapsed_sec: float = 0.0
    returncode: int | None = None
    output: str = ""
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "check": self.check.to_dict(),
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "returncode": self.returncode,
            "output": self.output,
            "error": self.error,
            "metadata": self.metadata,
        }


def _project_root() -> Path:
    return Path(__file__).resolve().parents[1]


def _python_check(
    check_id: str,
    title: str,
    modules: Sequence[str],
    *,
    python_exe: str,
    project_root: str,
    timeout_sec: int = 120,
    evidence: str = "",
) -> OperabilityCheck:
    return OperabilityCheck(
        id=check_id,
        title=title,
        category="backend",
        command=[python_exe, "-m", "unittest", *modules],
        cwd=project_root,
        timeout_sec=timeout_sec,
        evidence=evidence,
    )


def _frontend_check(
    check_id: str,
    title: str,
    command: Sequence[str],
    *,
    project_root: str,
    timeout_sec: int = 120,
    evidence: str = "",
) -> OperabilityCheck:
    return OperabilityCheck(
        id=check_id,
        title=title,
        category="frontend",
        command=list(command),
        cwd=str(Path(project_root) / "apps" / "dsa-web"),
        timeout_sec=timeout_sec,
        evidence=evidence,
    )


def _resolve_executable(name: str) -> str:
    candidates = [name]
    if sys.platform == "win32" and not Path(name).suffix:
        candidates = [f"{name}.cmd", f"{name}.exe", name]

    for candidate in candidates:
        resolved = shutil.which(candidate)
        if resolved:
            return resolved
    return candidates[0]


def _url_join(base_url: str, path: str) -> str:
    return f"{base_url.rstrip('/')}/{path.lstrip('/')}"


def build_operability_checks(
    *,
    python_exe: str | None = None,
    project_root: str | Path | None = None,
    web_base_url: str = DEFAULT_WEB_BASE_URL,
) -> list[OperabilityCheck]:
    root = str(Path(project_root) if project_root is not None else _project_root())
    py = python_exe or sys.executable
    npm = _resolve_executable("npm")

    return [
        _python_check(
            "basic_query_no_ai",
            "Basic stock snapshot does not use AI",
            ["tests.test_basic_query_no_ai", "tests.test_market_data_cache"],
            python_exe=py,
            project_root=root,
            evidence="No-AI stock query endpoint, deterministic indicators, cache freshness.",
        ),
        _python_check(
            "feature_quota",
            "Feature-specific AI quota buckets",
            ["tests.test_platform_feature_policy", "tests.test_platform_ai_feature_quota"],
            python_exe=py,
            project_root=root,
            evidence="Quick/deep/user-key quota buckets and limits.",
        ),
        _python_check(
            "user_api_key_mode",
            "User-owned API key mode",
            ["tests.test_platform_api_keys_product"],
            python_exe=py,
            project_root=root,
            evidence="Encrypted user API keys, provider/model metadata, no plaintext response.",
        ),
        _python_check(
            "local_model_capacity",
            "Local model capacity gate",
            ["tests.test_local_model_router"],
            python_exe=py,
            project_root=root,
            evidence="Optional local model concurrency and busy/disabled reasons.",
        ),
        _python_check(
            "security_boundaries",
            "Platform security boundaries",
            ["tests.test_platform_security_boundaries", "tests.test_platform_audit"],
            python_exe=py,
            project_root=root,
            evidence="CSRF toggle, admin boundary, secret redaction, audit trail.",
        ),
        _python_check(
            "billing_boundary",
            "Local V1 billing boundary",
            ["tests.test_billing_api"],
            python_exe=py,
            project_root=root,
            evidence="Billing disabled by default, webhook rejects missing signature.",
        ),
        _python_check(
            "admin_console_backend",
            "Admin operations backend endpoints",
            ["tests.test_platform_api"],
            python_exe=py,
            project_root=root,
            evidence="Admin users, usage buckets, audit events, plan changes.",
        ),
        _frontend_check(
            "admin_console_frontend",
            "Admin operations frontend",
            [
                npm,
                "test",
                "--",
                "src/api/__tests__/platform.test.ts",
                "src/pages/__tests__/AdminPage.test.tsx",
                "src/App.test.tsx",
                "src/components/layout/__tests__/SidebarNav.test.tsx",
            ],
            project_root=root,
            timeout_sec=120,
            evidence="Admin API client, /admin route, nav entry, dashboard rendering.",
        ),
        _frontend_check(
            "frontend_build",
            "Frontend production build",
            [npm, "run", "build"],
            project_root=root,
            timeout_sec=180,
            evidence="TypeScript and Vite production bundle.",
        ),
        OperabilityCheck(
            id="live_health",
            title="Live WebUI health",
            category="live",
            url=_url_join(web_base_url, "/health"),
            timeout_sec=10,
            evidence="Local service on 8018 responds with health OK.",
        ),
        OperabilityCheck(
            id="live_admin_page",
            title="Live admin page shell",
            category="live",
            url=_url_join(web_base_url, "/admin"),
            timeout_sec=10,
            evidence="SPA admin route returns the frontend shell.",
        ),
        OperabilityCheck(
            id="live_basic_snapshot",
            title="Optional live no-AI market snapshot",
            category="live",
            url=_url_join(web_base_url, "/api/v1/stocks/AAPL/snapshot"),
            optional=True,
            timeout_sec=30,
            evidence="Optional provider-backed snapshot smoke; can be slow/flaky if market data providers are unavailable.",
        ),
    ]


def _selected_checks(
    checks: Iterable[OperabilityCheck],
    *,
    include_optional: bool,
    only: set[str] | None = None,
) -> list[OperabilityCheck]:
    selected: list[OperabilityCheck] = []
    for check in checks:
        if check.optional and not include_optional:
            continue
        if only and check.id not in only:
            continue
        selected.append(check)
    return selected


def _run_command_check(check: OperabilityCheck) -> OperabilityResult:
    started = time.monotonic()
    try:
        completed = subprocess.run(
            check.command or [],
            cwd=check.cwd,
            timeout=check.timeout_sec,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
    except Exception as exc:
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=str(exc),
        )
    output = "\n".join(part for part in [completed.stdout, completed.stderr] if part)
    return OperabilityResult(
        check=check,
        status="passed" if completed.returncode == 0 else "failed",
        elapsed_sec=time.monotonic() - started,
        returncode=completed.returncode,
        output=output[-4000:],
    )


def _platform_smoke_credentials() -> tuple[str, str] | None:
    email = os.getenv("DSA_OPERABILITY_PLATFORM_EMAIL", "").strip()
    password = os.getenv("DSA_OPERABILITY_PLATFORM_PASSWORD", "")
    if not email or not password:
        return None
    return email, password


def _generate_auto_smoke_credentials() -> tuple[str, str]:
    timestamp = int(time.time())
    nonce = secrets.token_hex(4)
    email = f"e2e+local-smoke-{timestamp}-{nonce}@example.com"
    password = f"local-smoke-{secrets.token_urlsafe(18)}"
    return email, password


def _live_check_base_url(check: OperabilityCheck) -> str:
    url = check.url or DEFAULT_WEB_BASE_URL
    return url.split("/api/v1/", 1)[0].rstrip("/")


def _run_platform_auto_smoke_user_check(check: OperabilityCheck, *, started: float) -> OperabilityResult:
    email, password = _generate_auto_smoke_credentials()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    register_url = _url_join(_live_check_base_url(check), "/api/v1/platform/register")
    register_request = urllib.request.Request(
        register_url,
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    snapshot_request = urllib.request.Request(check.url or "", headers={"Accept": "application/json"})

    try:
        with opener.open(register_request, timeout=min(check.timeout_sec, 15)) as register_response:
            register_status = getattr(register_response, "status", register_response.getcode())
            register_response.read(4096)
        if not 200 <= int(register_status) < 400:
            return OperabilityResult(
                check=check,
                status="failed",
                elapsed_sec=time.monotonic() - started,
                error=f"platform smoke user registration failed: HTTP {register_status}",
                metadata={
                    "status_code": register_status,
                    "auth": "platform_auto_smoke_user",
                    "smoke_email": email,
                    "cleanup_prefix": "e2e+",
                },
            )
        with opener.open(snapshot_request, timeout=check.timeout_sec) as response:
            status_code = getattr(response, "status", response.getcode())
            body = response.read(4096).decode("utf-8", errors="replace")
    except HTTPError as exc:
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=f"HTTP Error {exc.code}: {exc.reason}",
            metadata={
                "status_code": exc.code,
                "auth": "platform_auto_smoke_user",
                "smoke_email": email,
                "cleanup_prefix": "e2e+",
            },
        )
    except Exception as exc:
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=str(exc),
            metadata={"auth": "platform_auto_smoke_user", "smoke_email": email, "cleanup_prefix": "e2e+"},
        )

    return OperabilityResult(
        check=check,
        status="passed" if 200 <= int(status_code) < 400 else "failed",
        elapsed_sec=time.monotonic() - started,
        output=body,
        metadata={
            "status_code": status_code,
            "auth": "platform_auto_smoke_user",
            "smoke_email": email,
            "cleanup_prefix": "e2e+",
        },
    )


def _run_platform_authenticated_url_check(
    check: OperabilityCheck,
    *,
    started: float,
    auto_smoke_user: bool = False,
) -> OperabilityResult:
    credentials = _platform_smoke_credentials()
    if credentials is None:
        if auto_smoke_user:
            return _run_platform_auto_smoke_user_check(check, started=started)
        return OperabilityResult(
            check=check,
            status="skipped",
            elapsed_sec=time.monotonic() - started,
            error=(
                "Live snapshot requires platform login. Set "
                "DSA_OPERABILITY_PLATFORM_EMAIL and DSA_OPERABILITY_PLATFORM_PASSWORD to run it."
            ),
            metadata={"reason": "missing_platform_smoke_credentials"},
        )

    email, password = credentials
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    login_url = _url_join(_live_check_base_url(check), "/api/v1/platform/login")
    login_request = urllib.request.Request(
        login_url,
        data=json.dumps({"email": email, "password": password}).encode("utf-8"),
        headers={"Content-Type": "application/json", "Accept": "application/json"},
        method="POST",
    )
    snapshot_request = urllib.request.Request(check.url or "", headers={"Accept": "application/json"})

    try:
        with opener.open(login_request, timeout=min(check.timeout_sec, 15)) as login_response:
            login_status = getattr(login_response, "status", login_response.getcode())
            login_response.read(4096)
        if not 200 <= int(login_status) < 400:
            return OperabilityResult(
                check=check,
                status="failed",
                elapsed_sec=time.monotonic() - started,
                error=f"platform login failed: HTTP {login_status}",
                metadata={"status_code": login_status},
            )
        with opener.open(snapshot_request, timeout=check.timeout_sec) as response:
            status_code = getattr(response, "status", response.getcode())
            body = response.read(4096).decode("utf-8", errors="replace")
    except HTTPError as exc:
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=f"HTTP Error {exc.code}: {exc.reason}",
            metadata={"status_code": exc.code, "auth": "platform_cookie"},
        )
    except Exception as exc:
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=str(exc),
            metadata={"auth": "platform_cookie"},
        )

    return OperabilityResult(
        check=check,
        status="passed" if 200 <= int(status_code) < 400 else "failed",
        elapsed_sec=time.monotonic() - started,
        output=body,
        metadata={"status_code": status_code, "auth": "platform_cookie"},
    )


def _run_url_check(check: OperabilityCheck, *, auto_smoke_user: bool = False) -> OperabilityResult:
    started = time.monotonic()
    try:
        with urlopen(check.url or "", timeout=check.timeout_sec) as response:
            status_code = getattr(response, "status", response.getcode())
            body = response.read(4096).decode("utf-8", errors="replace")
    except HTTPError as exc:
        if check.id == "live_basic_snapshot" and exc.code == 401:
            return _run_platform_authenticated_url_check(
                check,
                started=started,
                auto_smoke_user=auto_smoke_user,
            )
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=f"HTTP Error {exc.code}: {exc.reason}",
            metadata={"status_code": exc.code},
        )
    except Exception as exc:
        return OperabilityResult(
            check=check,
            status="failed",
            elapsed_sec=time.monotonic() - started,
            error=str(exc),
        )
    return OperabilityResult(
        check=check,
        status="passed" if 200 <= int(status_code) < 400 else "failed",
        elapsed_sec=time.monotonic() - started,
        output=body,
        metadata={"status_code": status_code},
    )


def run_operability_checks(
    *,
    dry_run: bool = False,
    include_optional: bool = False,
    auto_smoke_user: bool = False,
    python_exe: str | None = None,
    project_root: str | Path | None = None,
    web_base_url: str = DEFAULT_WEB_BASE_URL,
    only: Sequence[str] | None = None,
) -> list[OperabilityResult]:
    checks = build_operability_checks(
        python_exe=python_exe,
        project_root=project_root,
        web_base_url=web_base_url,
    )
    selected = _selected_checks(checks, include_optional=include_optional, only=set(only or []) or None)
    if dry_run:
        return [OperabilityResult(check=check, status="planned") for check in selected]

    results: list[OperabilityResult] = []
    for check in selected:
        if check.command:
            results.append(_run_command_check(check))
        elif check.url:
            results.append(_run_url_check(check, auto_smoke_user=auto_smoke_user))
        else:
            results.append(OperabilityResult(check=check, status="failed", error="check has no command or url"))
    return results


def _print_text_report(results: Sequence[OperabilityResult]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[--]" if result.status in {"planned", "skipped"} else "[FAIL]"
        print(f"{marker} {result.check.id}: {result.check.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.returncode is not None:
            print(f"  returncode: {result.returncode}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run DSA Local V1 platform operability checks")
    parser.add_argument("--dry-run", action="store_true", help="Print planned checks without executing commands or HTTP requests")
    parser.add_argument("--include-optional", action="store_true", help="Include optional live market provider checks")
    parser.add_argument(
        "--auto-smoke-user",
        action="store_true",
        help="Opt-in local-only helper: register an e2e+local-smoke user if live snapshot needs login.",
    )
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable used for backend unittest checks")
    parser.add_argument("--project-root", default=str(_project_root()), help="DSA project root")
    parser.add_argument("--base-url", default=DEFAULT_WEB_BASE_URL, help="Running WebUI base URL")
    parser.add_argument("--only", action="append", default=[], help="Run only a specific check id; can be repeated")
    args = parser.parse_args(argv)

    results = run_operability_checks(
        dry_run=args.dry_run,
        include_optional=args.include_optional,
        auto_smoke_user=args.auto_smoke_user,
        python_exe=args.python_exe,
        project_root=args.project_root,
        web_base_url=args.base_url,
        only=args.only,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status in {"passed", "planned", "skipped"} for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

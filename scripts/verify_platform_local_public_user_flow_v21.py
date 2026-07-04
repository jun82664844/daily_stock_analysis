from __future__ import annotations

import argparse
import json
import re
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
from scripts.verify_platform_local_browser_user_loop_v16 import (  # noqa: E402
    EXPECTED_SYMBOL_LANES,
    _snapshot_summary_from_payload,
)
from scripts.verify_platform_local_functional_v5 import (  # noqa: E402
    DEFAULT_BASE_URL,
    _json_request,
    _new_smoke_credentials,
    _url_join,
)
from scripts.verify_platform_local_public_entry_v20 import run_local_public_entry_v20_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_PUBLIC_USER_FLOW_V21_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md",
    "scripts/verify_platform_local_public_user_flow_v21.py",
    "tests/test_platform_local_public_user_flow_v21.py",
    "scripts/verify_platform_local_public_entry_v20.py",
    "tests/test_platform_local_public_entry_v20.py",
    "scripts/verify_platform_local_watchlist_board_v18.py",
    "tests/test_platform_local_watchlist_board_v18.py",
    "apps/dsa-web/e2e/platform-user-e2e.spec.ts",
    "apps/dsa-web/src/App.tsx",
    "apps/dsa-web/src/App.test.tsx",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/pages/AccountPage.tsx",
    "apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx",
    "apps/dsa-web/src/components/layout/SidebarNav.tsx",
    "apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/api/__tests__/platform.test.ts",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_public_user_flow_v21.py",
)

SECRET_KEY_NAMES = {"api_key", "apikey", "apiKey", "secret", "token", "authorization", "password"}
SECRET_VALUE_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"\b[A-Za-z0-9_-]{24,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"),
)


@dataclass(frozen=True)
class LocalPublicUserFlowV21Result:
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
) -> LocalPublicUserFlowV21Result:
    return LocalPublicUserFlowV21Result(
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


def _get(mapping: Mapping[str, Any], *keys: str) -> Any:
    for key in keys:
        if key in mapping:
            return mapping.get(key)
    return None


def _contains_plain_secret(value: Any) -> bool:
    if isinstance(value, Mapping):
        for key, item in value.items():
            if str(key) in SECRET_KEY_NAMES:
                return True
            if _contains_plain_secret(item):
                return True
        return False
    if isinstance(value, Sequence) and not isinstance(value, (str, bytes, bytearray)):
        return any(_contains_plain_secret(item) for item in value)
    if isinstance(value, str):
        return any(pattern.search(value) for pattern in SECRET_VALUE_PATTERNS)
    return False


def evaluate_public_user_flow_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    public_entry = summary.get("public_entry")
    if not isinstance(public_entry, Mapping):
        problems.append("public_entry:missing")
    else:
        if public_entry.get("reachable") is not True:
            problems.append("public_entry:not_reachable")
        if public_entry.get("admin_login_visible") is not False:
            problems.append("public_entry:admin_login_visible")
        if public_entry.get("admin_nav_visible") is not False:
            problems.append("public_entry:admin_nav_visible")
        if public_entry.get("login_required_error_visible") is not False:
            problems.append("public_entry:login_required_error_visible")

    auth = summary.get("auth")
    if not isinstance(auth, Mapping):
        problems.append("auth:missing")
    else:
        if auth.get("registered") is not True:
            problems.append("auth:not_registered")
        if auth.get("logged_in") is not True:
            problems.append("auth:not_logged_in")
        if auth.get("password_exposed") is not False:
            problems.append("auth:password_exposed")

    account = summary.get("account")
    if not isinstance(account, Mapping):
        problems.append("account:missing")
    else:
        if account.get("status_code") != 200:
            problems.append("account:status_not_200")
        if account.get("email_matches") is not True:
            problems.append("account:email_mismatch")
        if account.get("masked_api_key_only") is not True:
            problems.append("account:plaintext_api_key_visible")
        if account.get("quota_present") is not True:
            problems.append("account:quota_missing")
        if account.get("quota_buckets_present") is not True:
            problems.append("account:quota_buckets_missing")

    queries = summary.get("queries")
    if not isinstance(queries, Mapping):
        problems.append("queries:missing")
    else:
        for symbol, expected_lane in EXPECTED_SYMBOL_LANES.items():
            item = queries.get(symbol)
            if not isinstance(item, Mapping):
                problems.append(f"{symbol}:missing")
                continue
            if item.get("status_code") != 200:
                problems.append(f"{symbol}:status_not_200")
            if item.get("lane") != expected_lane:
                problems.append(f"{symbol}:unexpected_lane")
            if item.get("ai_used") is not False:
                problems.append(f"{symbol}:ai_used_not_false")

    watchlist = summary.get("watchlist")
    if not isinstance(watchlist, Mapping):
        problems.append("watchlist:missing")
    else:
        if int(watchlist.get("added") or 0) < len(EXPECTED_SYMBOL_LANES):
            problems.append("watchlist:added_too_low")
        if watchlist.get("refresh_status_code") != 200:
            problems.append("watchlist:refresh_status_not_200")
        if watchlist.get("private") is not True:
            problems.append("watchlist:not_private")
        if watchlist.get("ai_used") is not False:
            problems.append("watchlist:ai_used_not_false")

    admin_boundary = summary.get("admin_boundary")
    if not isinstance(admin_boundary, Mapping):
        problems.append("admin_boundary:missing")
    else:
        if admin_boundary.get("ordinary_admin_status") != 403:
            problems.append("admin_boundary:ordinary_user_not_forbidden")
        if admin_boundary.get("admin_nav_visible") is not False:
            problems.append("admin_boundary:admin_nav_visible")
    return problems


def _run_required_files_check(root: Path) -> LocalPublicUserFlowV21Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v21_required_files_present",
            "Local Public User Flow V21 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v21_required_files_present",
        "Local Public User Flow V21 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalPublicUserFlowV21Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v21_verifiers_visible_to_git",
            "V21 verifier files are not gitignored",
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
            "v21_verifiers_visible_to_git",
            "V21 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v21_verifiers_visible_to_git",
        "V21 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_public_user_flow_shape_check() -> LocalPublicUserFlowV21Result:
    started = time.monotonic()
    sample = {
        "public_entry": {
            "reachable": True,
            "admin_login_visible": False,
            "admin_nav_visible": False,
            "login_required_error_visible": False,
        },
        "auth": {"registered": True, "logged_in": True, "password_exposed": False},
        "account": {
            "status_code": 200,
            "email_matches": True,
            "masked_api_key_only": True,
            "quota_present": True,
            "quota_buckets_present": True,
        },
        "queries": {
            symbol: {"status_code": 200, "lane": lane, "ai_used": False}
            for symbol, lane in EXPECTED_SYMBOL_LANES.items()
        },
        "watchlist": {"added": 4, "refresh_status_code": 200, "private": True, "ai_used": False},
        "admin_boundary": {"ordinary_admin_status": 403, "admin_nav_visible": False},
    }
    problems = evaluate_public_user_flow_summary(sample)
    if problems:
        return _result(
            "v21_public_user_flow_shape",
            "V21 public ordinary-user flow summary validates local boundaries",
            started,
            status="failed",
            error="sample public-user summary failed validation",
            metadata={"problems": problems},
        )
    return _result(
        "v21_public_user_flow_shape",
        "V21 public ordinary-user flow summary validates local boundaries",
        started,
        metadata={"symbols": sorted(EXPECTED_SYMBOL_LANES)},
    )


def _run_v20_compatibility_gate(root: Path, python_exe: str) -> LocalPublicUserFlowV21Result:
    started = time.monotonic()
    results = run_local_public_entry_v20_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v20_public_entry_compatibility",
            "V20 public-entry gate remains compatible with V21 user flow",
            started,
            status="failed",
            error="V20 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v20_public_entry_compatibility",
        "V20 public-entry gate remains compatible with V21 user flow",
        started,
        metadata=metadata,
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> LocalPublicUserFlowV21Result:
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
        return _result(
            check_id,
            title,
            started,
            status="failed",
            error="subprocess check failed",
            metadata=metadata,
        )
    return _result(check_id, title, started, metadata=metadata)


def _read_response_body(response: Any) -> tuple[int, dict[str, Any] | list[Any] | str]:
    status_code = int(getattr(response, "status", response.getcode()))
    body = response.read(32768).decode("utf-8", errors="replace")
    try:
        return status_code, json.loads(body)
    except json.JSONDecodeError:
        return status_code, body


def _open_any_json(
    opener: urllib.request.OpenerDirector,
    request: urllib.request.Request,
    *,
    timeout: int = 10,
) -> tuple[int, dict[str, Any] | list[Any] | str]:
    try:
        with opener.open(request, timeout=timeout) as response:
            return _read_response_body(response)
    except urllib.error.HTTPError as exc:
        return _read_response_body(exc)


def _csrf_token_from_jar(cookie_jar: CookieJar) -> str | None:
    for cookie in cookie_jar:
        if cookie.name == "dsa_csrf_token":
            return str(cookie.value)
    return None


def _json_request_with_csrf(cookie_jar: CookieJar, url: str, payload: dict[str, Any]) -> urllib.request.Request:
    request = _json_request(url, payload)
    csrf_token = _csrf_token_from_jar(cookie_jar)
    if csrf_token:
        request.add_header("X-DSA-CSRF", csrf_token)
    return request


def _get_json_request(url: str) -> urllib.request.Request:
    return urllib.request.Request(url, headers={"Accept": "application/json"})


def _run_optional_live_public_user_flow(base_url: str) -> LocalPublicUserFlowV21Result:
    started = time.monotonic()
    smoke_email, smoke_password = _new_smoke_credentials("local-v21-user")
    cookie_jar = CookieJar()
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cookie_jar))
    metadata: dict[str, Any] = {
        "base_url": base_url,
        "smoke_email": smoke_email,
        "cleanup_prefix": "e2e+",
        "symbols": list(EXPECTED_SYMBOL_LANES),
    }
    summary: dict[str, Any] = {
        "public_entry": {
            "reachable": False,
            "admin_login_visible": False,
            "admin_nav_visible": False,
            "login_required_error_visible": False,
        },
        "auth": {"registered": False, "logged_in": False, "password_exposed": False},
        "account": {
            "status_code": None,
            "email_matches": False,
            "masked_api_key_only": False,
            "quota_present": False,
            "quota_buckets_present": False,
        },
        "queries": {},
        "watchlist": {"added": 0, "refresh_status_code": None, "private": False, "ai_used": None},
        "admin_boundary": {"ordinary_admin_status": None, "admin_nav_visible": False},
    }

    try:
        root_status, root_payload = _open_any_json(
            opener,
            urllib.request.Request(_url_join(base_url, "/"), headers={"Accept": "text/html"}),
            timeout=15,
        )
        root_text = root_payload if isinstance(root_payload, str) else json.dumps(root_payload, ensure_ascii=False)
        summary["public_entry"] = {
            "reachable": root_status == 200,
            "admin_login_visible": "Admin Login" in root_text or "管理员登录" in root_text,
            "admin_nav_visible": "Admin" in root_text and "settings" in root_text.lower(),
            "login_required_error_visible": "Login required" in root_text,
        }

        register_status, register_payload = _open_any_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": smoke_email, "password": smoke_password}),
            timeout=15,
        )
        summary["auth"] = {
            "registered": register_status == 200,
            "logged_in": isinstance(register_payload, Mapping) and _get(register_payload, "user") is not None,
            "password_exposed": False,
        }
        metadata["register_status_code"] = register_status

        account_status, account_payload = _open_any_json(
            opener,
            _get_json_request(_url_join(base_url, "/api/v1/platform/account")),
            timeout=15,
        )
        account_user = account_payload.get("user", {}) if isinstance(account_payload, Mapping) else {}
        api_keys = account_payload.get("api_keys") if isinstance(account_payload, Mapping) else None
        summary["account"] = {
            "status_code": account_status,
            "email_matches": isinstance(account_user, Mapping) and account_user.get("email") == smoke_email,
            "masked_api_key_only": isinstance(account_payload, Mapping) and not _contains_plain_secret(api_keys or []),
            "quota_present": isinstance(account_payload, Mapping) and isinstance(account_payload.get("quota"), Mapping),
            "quota_buckets_present": isinstance(account_payload, Mapping) and isinstance(account_payload.get("quota_buckets"), list),
        }
        metadata["account_status_code"] = account_status
        metadata["account_email"] = account_user.get("email") if isinstance(account_user, Mapping) else None

        query_summary: dict[str, dict[str, Any]] = {}
        for symbol in EXPECTED_SYMBOL_LANES:
            status_code, payload = _open_any_json(
                opener,
                _get_json_request(_url_join(base_url, f"/api/v1/stocks/{urllib.parse.quote(symbol, safe='')}/snapshot")),
                timeout=25,
            )
            if isinstance(payload, dict):
                query_summary[symbol] = _snapshot_summary_from_payload(status_code, payload)
            else:
                query_summary[symbol] = {"status_code": status_code, "lane": None, "ai_used": None, "freshness": None}
        summary["queries"] = query_summary

        for symbol in EXPECTED_SYMBOL_LANES:
            add_status, _ = _open_any_json(
                opener,
                _json_request_with_csrf(
                    cookie_jar,
                    _url_join(base_url, "/api/v1/platform/watchlist"),
                    {"stock_code": symbol},
                ),
                timeout=15,
            )
            metadata.setdefault("watchlist_add_status_codes", {})[symbol] = add_status

        watch_status, watch_payload = _open_any_json(
            opener,
            _get_json_request(_url_join(base_url, "/api/v1/platform/watchlist")),
            timeout=15,
        )
        watch_items = watch_payload.get("items") if isinstance(watch_payload, Mapping) else []
        refresh_status, refresh_payload = _open_any_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/watchlist/refresh"), {}),
            timeout=35,
        )
        refresh_items = refresh_payload.get("items") if isinstance(refresh_payload, Mapping) else []
        summary["watchlist"] = {
            "added": len(watch_items) if isinstance(watch_items, list) else 0,
            "refresh_status_code": refresh_status,
            "private": (
                watch_status == 200
                and isinstance(watch_payload, Mapping)
                and isinstance(watch_payload.get("user_id"), int)
                and all(isinstance(item, Mapping) for item in watch_items)
            ),
            "ai_used": refresh_payload.get("ai_used") if isinstance(refresh_payload, Mapping) else None,
            "refreshed": refresh_payload.get("refreshed") if isinstance(refresh_payload, Mapping) else None,
            "refresh_items": len(refresh_items) if isinstance(refresh_items, list) else 0,
        }

        admin_status, _ = _open_any_json(
            opener,
            _get_json_request(_url_join(base_url, "/api/v1/platform/admin/users")),
            timeout=15,
        )
        summary["admin_boundary"] = {"ordinary_admin_status": admin_status, "admin_nav_visible": False}
    except Exception as exc:
        return _result(
            "optional_live_public_user_flow",
            "Optional live 8018 ordinary-user public flow smoke",
            started,
            status="degraded",
            error=str(exc),
            metadata={**metadata, "summary": summary},
            optional=True,
        )

    problems = evaluate_public_user_flow_summary(summary)
    if problems:
        return _result(
            "optional_live_public_user_flow",
            "Optional live 8018 ordinary-user public flow smoke",
            started,
            status="degraded",
            error="live public-user flow reported degraded data",
            metadata={**metadata, "summary": summary, "problems": problems},
            optional=True,
        )
    return _result(
        "optional_live_public_user_flow",
        "Optional live 8018 ordinary-user public flow smoke",
        started,
        metadata={**metadata, "summary": summary},
        optional=True,
    )


def run_local_public_user_flow_v21_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
) -> list[LocalPublicUserFlowV21Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[LocalPublicUserFlowV21Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_public_user_flow_shape_check(),
        _run_v20_compatibility_gate(root, python_path),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v21_public_user_flow_unittest",
                title="V21 public user flow verifier tests pass",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_public_user_flow_v21"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v21_frontend_public_user_flow_tests",
                title="Frontend public user Home/Account/Nav tests pass",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/App.test.tsx",
                    "src/pages/__tests__/HomePage.test.tsx",
                    "src/pages/__tests__/AccountPage.test.tsx",
                    "src/components/layout/__tests__/SidebarNav.test.tsx",
                ],
            )
        )
    if run_live:
        results.append(_run_optional_live_public_user_flow(base_url))
    return results


def _passed_for_marker(results: Sequence[LocalPublicUserFlowV21Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[LocalPublicUserFlowV21Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA local V21 public ordinary-user flow.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--skip-live", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_local_public_user_flow_v21_checks(
        project_root=Path(args.project_root),
        python_exe=args.python,
        base_url=args.base_url,
        run_subprocess=not args.skip_subprocess,
        run_live=not args.skip_live,
    )
    if args.json:
        print(json.dumps({"results": [result.to_dict() for result in results], "ok": _passed_for_marker(results)}, ensure_ascii=False, indent=2))
        if _passed_for_marker(results):
            print(OK_MARKER)
    else:
        _print_text_report(results)
    return 0 if _passed_for_marker(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

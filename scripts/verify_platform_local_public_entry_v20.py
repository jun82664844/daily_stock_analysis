from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_local_v1_operability import _resolve_executable  # noqa: E402
from scripts.verify_platform_local_query_workspace_v19 import run_local_query_workspace_v19_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md",
    "scripts/verify_platform_local_public_entry_v20.py",
    "tests/test_platform_local_public_entry_v20.py",
    "apps/dsa-web/src/App.tsx",
    "apps/dsa-web/src/App.test.tsx",
    "apps/dsa-web/src/api/index.ts",
    "apps/dsa-web/src/api/__tests__/index.test.ts",
    "apps/dsa-web/src/components/layout/SidebarNav.tsx",
    "apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx",
    "apps/dsa-web/src/stores/stockPoolStore.ts",
    "apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_public_entry_v20.py",
)

PUBLIC_USER_ROUTES = ("/", "/portfolio", "/chat", "/account", "/usage")
ADMIN_ONLY_ROUTES = ("/admin", "/settings")


@dataclass(frozen=True)
class LocalPublicEntryV20Result:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
        }


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict[str, Any] | None = None,
) -> LocalPublicEntryV20Result:
    return LocalPublicEntryV20Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
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


def evaluate_public_entry_routes(routes: Mapping[str, Mapping[str, Any]] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(routes, Mapping):
        return ["routes:missing"]

    for route_path in PUBLIC_USER_ROUTES:
        route = routes.get(route_path)
        if not isinstance(route, Mapping):
            problems.append(f"{route_path}:missing")
            continue
        if route.get("requires_admin") is not False:
            problems.append(f"{route_path}:admin_gate_blocks_public_entry")

    login_route = routes.get("/login")
    if not isinstance(login_route, Mapping):
        problems.append("/login:missing")
    else:
        if login_route.get("requires_admin") is not False:
            problems.append("/login:requires_admin")
        if login_route.get("admin_login") is not True:
            problems.append("/login:not_admin_login")

    for route_path in ADMIN_ONLY_ROUTES:
        route = routes.get(route_path)
        if not isinstance(route, Mapping):
            problems.append(f"{route_path}:missing")
            continue
        if route.get("requires_admin") is not True:
            problems.append(f"{route_path}:admin_route_unprotected")
    return problems


def _run_required_files_check(root: Path) -> LocalPublicEntryV20Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v20_required_files_present",
            "Local Public Entry V20 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v20_required_files_present",
        "Local Public Entry V20 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalPublicEntryV20Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v20_verifiers_visible_to_git",
            "V20 verifier files are not gitignored",
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
            "v20_verifiers_visible_to_git",
            "V20 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v20_verifiers_visible_to_git",
        "V20 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_public_entry_shape_check() -> LocalPublicEntryV20Result:
    started = time.monotonic()
    sample = {
        "/": {"requires_admin": False, "page": "home"},
        "/portfolio": {"requires_admin": False, "page": "portfolio"},
        "/chat": {"requires_admin": False, "page": "chat"},
        "/account": {"requires_admin": False, "page": "account"},
        "/usage": {"requires_admin": False, "page": "usage"},
        "/login": {"requires_admin": False, "admin_login": True},
        "/admin": {"requires_admin": True, "page": "admin"},
        "/settings": {"requires_admin": True, "page": "settings"},
    }
    problems = evaluate_public_entry_routes(sample)
    if problems:
        return _result(
            "v20_public_entry_route_shape",
            "V20 route model separates public user entry from admin-only pages",
            started,
            status="failed",
            error="sample public entry route model failed validation",
            metadata={"problems": problems},
        )
    return _result(
        "v20_public_entry_route_shape",
        "V20 route model separates public user entry from admin-only pages",
        started,
        metadata={"public_routes": sorted(PUBLIC_USER_ROUTES), "admin_routes": sorted(ADMIN_ONLY_ROUTES)},
    )


def _run_v19_compatibility_gate(root: Path, python_exe: str) -> LocalPublicEntryV20Result:
    started = time.monotonic()
    results = run_local_query_workspace_v19_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v19_query_workspace_compatibility",
            "V19 query workspace gate remains compatible with V20 public entry",
            started,
            status="failed",
            error="V19 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v19_query_workspace_compatibility",
        "V19 query workspace gate remains compatible with V20 public entry",
        started,
        metadata=metadata,
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> LocalPublicEntryV20Result:
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


def run_local_public_entry_v20_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[LocalPublicEntryV20Result]:
    root = project_root.resolve()
    python_path = python_exe or sys.executable
    results: list[LocalPublicEntryV20Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_public_entry_shape_check(),
        _run_v19_compatibility_gate(root, python_path),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v20_public_entry_unittest",
                title="V20 public entry verifier tests pass",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_public_entry_v20"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v20_frontend_app_route_guard_test",
                title="Frontend App route guard keeps public entry open and admin protected",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/App.test.tsx",
                ],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v20_frontend_api_401_redirect_test",
                title="Frontend API 401 redirect guard does not send public platform entry to admin login",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/api/__tests__/index.test.ts",
                ],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v20_frontend_public_nav_guard_test",
                title="Frontend public navigation hides admin-only entries before admin login",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/components/layout/__tests__/SidebarNav.test.tsx",
                ],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v20_frontend_public_history_401_guard_test",
                title="Frontend public entry treats unauthenticated history loads as empty state",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/stores/__tests__/stockPoolStore.test.ts",
                    "-t",
                    "unauthenticated",
                ],
            )
        )
    return results


def _print_results(results: Sequence[LocalPublicEntryV20Result]) -> None:
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA local V20 public platform entry loop.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_local_public_entry_v20_checks(
        project_root=Path(args.project_root),
        python_exe=args.python,
        run_subprocess=not args.skip_subprocess,
    )
    failed = [result for result in results if result.status == "failed"]
    if args.json:
        print(json.dumps({"results": [result.to_dict() for result in results], "ok": not failed}, ensure_ascii=False, indent=2))
    else:
        _print_results(results)
    if failed:
        print("DSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

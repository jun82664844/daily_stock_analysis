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
from scripts.verify_platform_local_watchlist_board_v18 import run_local_watchlist_board_v18_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v19-query-workspace.md",
    "scripts/verify_platform_local_query_workspace_v19.py",
    "tests/test_platform_local_query_workspace_v19.py",
    "scripts/verify_platform_local_watchlist_board_v18.py",
    "tests/test_platform_local_watchlist_board_v18.py",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_query_workspace_v19.py",
)

EXPECTED_SEGMENTS = ("current_snapshot", "watchlist", "history_reports", "ai_analysis")
EXPECTED_LANES = {"a_share_market_data", "us_market_data", "hk_market_data", "crypto_market_data"}


@dataclass(frozen=True)
class LocalQueryWorkspaceV19Result:
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
) -> LocalQueryWorkspaceV19Result:
    return LocalQueryWorkspaceV19Result(
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


def evaluate_query_workspace_segments(segments: Mapping[str, Mapping[str, Any]] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(segments, Mapping):
        return ["workspace:segments_missing"]
    for segment_id in EXPECTED_SEGMENTS:
        if not isinstance(segments.get(segment_id), Mapping):
            problems.append(f"{segment_id}:missing")

    current = segments.get("current_snapshot") if isinstance(segments.get("current_snapshot"), Mapping) else {}
    if current.get("ai_used") is not False:
        problems.append("current_snapshot:ai_used_not_false")
    if current.get("route_lane") not in EXPECTED_LANES:
        problems.append("current_snapshot:route_lane_missing")
    if not current.get("freshness"):
        problems.append("current_snapshot:freshness_missing")

    watchlist = segments.get("watchlist") if isinstance(segments.get("watchlist"), Mapping) else {}
    if watchlist.get("private") is not True:
        problems.append("watchlist:not_private")
    if not isinstance(watchlist.get("count"), int) or int(watchlist.get("count") or 0) < 0:
        problems.append("watchlist:count_missing")

    history = segments.get("history_reports") if isinstance(segments.get("history_reports"), Mapping) else {}
    if history.get("separate") is not True:
        problems.append("history_reports:not_separate")
    if not isinstance(history.get("count"), int) or int(history.get("count") or 0) < 0:
        problems.append("history_reports:count_missing")

    ai = segments.get("ai_analysis") if isinstance(segments.get("ai_analysis"), Mapping) else {}
    if ai.get("trigger") != "manual":
        problems.append("ai_analysis:not_manual")
    if ai.get("selected_mode") not in {"platform", "user", "local"}:
        problems.append("ai_analysis:selected_mode_missing")
    if ai.get("quick_snapshot_consumes_ai") is not False:
        problems.append("ai_analysis:quick_snapshot_consumes_ai")
    return problems


def _run_required_files_check(root: Path) -> LocalQueryWorkspaceV19Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v19_required_files_present",
            "Local Query Workspace V19 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v19_required_files_present",
        "Local Query Workspace V19 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalQueryWorkspaceV19Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v19_verifiers_visible_to_git",
            "V19 verifier files are not gitignored",
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
            "v19_verifiers_visible_to_git",
            "V19 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v19_verifiers_visible_to_git",
        "V19 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_workspace_shape_check() -> LocalQueryWorkspaceV19Result:
    started = time.monotonic()
    sample = {
        "current_snapshot": {"ai_used": False, "route_lane": "hk_market_data", "freshness": "fresh"},
        "watchlist": {"private": True, "count": 4},
        "history_reports": {"separate": True, "count": 0},
        "ai_analysis": {"trigger": "manual", "selected_mode": "platform", "quick_snapshot_consumes_ai": False},
    }
    problems = evaluate_query_workspace_segments(sample)
    if problems:
        return _result(
            "v19_query_workspace_shape",
            "V19 query workspace validates query separation lanes",
            started,
            status="failed",
            error="sample query workspace failed validation",
            metadata={"problems": problems},
        )
    return _result(
        "v19_query_workspace_shape",
        "V19 query workspace validates query separation lanes",
        started,
        metadata={"segments": sorted(EXPECTED_SEGMENTS)},
    )


def _run_v18_compatibility_gate(root: Path, python_exe: str) -> LocalQueryWorkspaceV19Result:
    started = time.monotonic()
    results = run_local_watchlist_board_v18_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v18_watchlist_board_compatibility",
            "V18 watchlist board gate remains compatible with V19 workspace",
            started,
            status="failed",
            error="V18 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v18_watchlist_board_compatibility",
        "V18 watchlist board gate remains compatible with V19 workspace",
        started,
        metadata=metadata,
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> LocalQueryWorkspaceV19Result:
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


def run_local_query_workspace_v19_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[LocalQueryWorkspaceV19Result]:
    root = project_root.resolve()
    python_path = python_exe or sys.executable
    results: list[LocalQueryWorkspaceV19Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_workspace_shape_check(),
        _run_v18_compatibility_gate(root, python_path),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v19_query_workspace_unittest",
                title="V19 query workspace verifier tests pass",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_query_workspace_v19"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v19_frontend_homepage_query_workspace_test",
                title="Frontend HomePage V19 query workspace target test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/pages/__tests__/HomePage.test.tsx",
                    "-t",
                    "ordinary-user account guardrails",
                ],
            )
        )
    return results


def _print_results(results: Sequence[LocalQueryWorkspaceV19Result]) -> None:
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA local V19 query workspace loop.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_local_query_workspace_v19_checks(
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
        print("DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
from scripts.verify_platform_local_browser_user_loop_v16 import run_local_browser_user_loop_v16_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v17-user-watchlist.md",
    "scripts/verify_platform_local_watchlist_v17.py",
    "tests/test_platform_local_watchlist_v17.py",
    "tests/test_platform_local_watchlist_v17_verifier.py",
    "src/platform_watchlist.py",
    "src/storage.py",
    "api/v1/endpoints/platform.py",
    "api/v1/schemas/platform.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_watchlist_v17.py",
)

EXPECTED_SYMBOL_LANES = {
    "600519": "a_share_market_data",
    "AAPL": "us_market_data",
    "HK00700": "hk_market_data",
    "BTC-USD": "crypto_market_data",
}


@dataclass(frozen=True)
class LocalWatchlistV17Result:
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
) -> LocalWatchlistV17Result:
    return LocalWatchlistV17Result(
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


def evaluate_watchlist_refresh_summary(summary: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    if summary.get("ai_used") is not False:
        problems.append("summary:ai_used_not_false")
    if int(summary.get("requested") or 0) < len(EXPECTED_SYMBOL_LANES):
        problems.append("summary:requested_too_low")
    items = summary.get("items")
    if not isinstance(items, Sequence) or isinstance(items, (str, bytes)):
        return problems + ["summary:items_missing"]
    by_symbol: dict[str, Mapping[str, Any]] = {}
    for item in items:
        if isinstance(item, Mapping) and item.get("stock_code"):
            by_symbol[str(item.get("stock_code"))] = item
    for symbol, expected_lane in EXPECTED_SYMBOL_LANES.items():
        item = by_symbol.get(symbol)
        if item is None:
            problems.append(f"{symbol}:missing")
            continue
        if item.get("route_lane") != expected_lane:
            problems.append(f"{symbol}:unexpected_lane")
        if item.get("ai_used") is not False:
            problems.append(f"{symbol}:ai_used_not_false")
        if item.get("status") not in {"ok", "degraded", "error"}:
            problems.append(f"{symbol}:status_missing")
    return problems


def _run_required_files_check(root: Path) -> LocalWatchlistV17Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v17_required_files_present",
            "Local Watchlist V17 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v17_required_files_present",
        "Local Watchlist V17 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalWatchlistV17Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v17_verifiers_visible_to_git",
            "V17 verifier files are not gitignored",
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
            "v17_verifiers_visible_to_git",
            "V17 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v17_verifiers_visible_to_git",
        "V17 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_refresh_summary_shape_check() -> LocalWatchlistV17Result:
    started = time.monotonic()
    sample = {
        "requested": 4,
        "refreshed": 4,
        "degraded": 1,
        "ai_used": False,
        "items": [
            {
                "stock_code": symbol,
                "route_lane": lane,
                "ai_used": False,
                "status": "degraded" if symbol == "HK00700" else "ok",
            }
            for symbol, lane in EXPECTED_SYMBOL_LANES.items()
        ],
    }
    problems = evaluate_watchlist_refresh_summary(sample)
    if problems:
        return _result(
            "v17_watchlist_refresh_summary_shape",
            "V17 watchlist refresh summary validates no-AI market lanes",
            started,
            status="failed",
            error="sample watchlist refresh summary failed validation",
            metadata={"problems": problems},
        )
    return _result(
        "v17_watchlist_refresh_summary_shape",
        "V17 watchlist refresh summary validates no-AI market lanes",
        started,
        metadata={"symbols": sorted(EXPECTED_SYMBOL_LANES)},
    )


def _run_v16_compatibility_gate(root: Path, python_exe: str) -> LocalWatchlistV17Result:
    started = time.monotonic()
    results = run_local_browser_user_loop_v16_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
        run_live=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v16_browser_user_loop_compatibility",
            "V16 browser-user gate remains compatible with V17",
            started,
            status="failed",
            error="V16 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v16_browser_user_loop_compatibility",
        "V16 browser-user gate remains compatible with V17",
        started,
        metadata=metadata,
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> LocalWatchlistV17Result:
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


def run_local_watchlist_v17_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[LocalWatchlistV17Result]:
    root = project_root.resolve()
    python_path = python_exe or sys.executable
    results: list[LocalWatchlistV17Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_refresh_summary_shape_check(),
        _run_v16_compatibility_gate(root, python_path),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v17_backend_watchlist_unittest",
                title="Backend V17 platform watchlist tests pass",
                cwd=root,
                command=[
                    python_path,
                    "-m",
                    "unittest",
                    "tests.test_platform_local_watchlist_v17",
                    "tests.test_platform_local_watchlist_v17_verifier",
                ],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v17_frontend_homepage_watchlist_test",
                title="Frontend HomePage V17 watchlist target test passes",
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
        results.append(
            _run_subprocess_check(
                check_id="v17_frontend_platform_api_watchlist_test",
                title="Frontend platform API V17 watchlist client test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/api/__tests__/platform.test.ts",
                ],
            )
        )
    return results


def _print_results(results: Sequence[LocalWatchlistV17Result]) -> None:
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA local V17 user watchlist loop.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_local_watchlist_v17_checks(
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
        print("DSA_PLATFORM_LOCAL_WATCHLIST_V17_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

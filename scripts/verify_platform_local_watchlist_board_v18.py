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
from scripts.verify_platform_local_watchlist_v17 import run_local_watchlist_v17_checks  # noqa: E402


OK_MARKER = "DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v18-watchlist-board.md",
    "scripts/verify_platform_local_watchlist_board_v18.py",
    "tests/test_platform_local_watchlist_board_v18.py",
    "scripts/verify_platform_local_watchlist_v17.py",
    "tests/test_platform_local_watchlist_v17.py",
    "src/platform_watchlist.py",
    "api/v1/endpoints/platform.py",
    "api/v1/schemas/platform.py",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_watchlist_board_v18.py",
)

EXPECTED_SYMBOL_LANES = {
    "600519": "a_share_market_data",
    "AAPL": "us_market_data",
    "HK00700": "hk_market_data",
    "BTC-USD": "crypto_market_data",
}


@dataclass(frozen=True)
class LocalWatchlistBoardV18Result:
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
) -> LocalWatchlistBoardV18Result:
    return LocalWatchlistBoardV18Result(
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


def _get(item: Mapping[str, Any], snake_key: str) -> Any:
    if snake_key in item:
        return item.get(snake_key)
    parts = snake_key.split("_")
    camel_key = parts[0] + "".join(part.capitalize() for part in parts[1:])
    return item.get(camel_key)


def _is_number(value: Any) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def evaluate_watchlist_board_rows(rows: Sequence[Mapping[str, Any]] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(rows, Sequence) or isinstance(rows, (str, bytes)):
        return ["board:rows_missing"]

    by_symbol: dict[str, Mapping[str, Any]] = {}
    for row in rows:
        if isinstance(row, Mapping) and _get(row, "stock_code"):
            by_symbol[str(_get(row, "stock_code"))] = row

    for symbol, expected_lane in EXPECTED_SYMBOL_LANES.items():
        row = by_symbol.get(symbol)
        if row is None:
            problems.append(f"{symbol}:missing")
            continue
        if not _get(row, "stock_name"):
            problems.append(f"{symbol}:stock_name_missing")
        if not _get(row, "market"):
            problems.append(f"{symbol}:market_missing")
        if _get(row, "route_lane") != expected_lane:
            problems.append(f"{symbol}:unexpected_lane")
        if not _is_number(_get(row, "current_price")):
            problems.append(f"{symbol}:price_missing")
        if not _is_number(_get(row, "change_percent")):
            problems.append(f"{symbol}:change_percent_missing")
        if not _get(row, "freshness"):
            problems.append(f"{symbol}:freshness_missing")
        if _get(row, "degradation_status") not in {"ok", "degraded", "error"}:
            problems.append(f"{symbol}:degradation_status_missing")
        if _get(row, "status") not in {"ok", "degraded", "error"}:
            problems.append(f"{symbol}:status_missing")
        if _get(row, "ai_used") is not False:
            problems.append(f"{symbol}:ai_used_not_false")
    return problems


def _run_required_files_check(root: Path) -> LocalWatchlistBoardV18Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v18_required_files_present",
            "Local Watchlist Board V18 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v18_required_files_present",
        "Local Watchlist Board V18 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> LocalWatchlistBoardV18Result:
    started = time.monotonic()
    if not _is_git_worktree(root):
        return _result(
            "v18_verifiers_visible_to_git",
            "V18 verifier files are not gitignored",
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
            "v18_verifiers_visible_to_git",
            "V18 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v18_verifiers_visible_to_git",
        "V18 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES), "git_worktree": True},
    )


def _run_board_shape_check() -> LocalWatchlistBoardV18Result:
    started = time.monotonic()
    sample_rows = [
        {
            "stock_code": symbol,
            "stock_name": f"{symbol} name",
            "market": "hk" if symbol == "HK00700" else "crypto" if symbol == "BTC-USD" else "us" if symbol == "AAPL" else "cn",
            "route_lane": lane,
            "current_price": 100.0,
            "change_percent": 1.2,
            "freshness": "fresh",
            "degradation_status": "degraded" if symbol == "HK00700" else "ok",
            "warning_codes": ["missing_history"] if symbol == "HK00700" else [],
            "ai_used": False,
            "status": "degraded" if symbol == "HK00700" else "ok",
        }
        for symbol, lane in EXPECTED_SYMBOL_LANES.items()
    ]
    problems = evaluate_watchlist_board_rows(sample_rows)
    if problems:
        return _result(
            "v18_watchlist_board_shape",
            "V18 watchlist board rows validate no-AI multi-market fields",
            started,
            status="failed",
            error="sample watchlist board rows failed validation",
            metadata={"problems": problems},
        )
    return _result(
        "v18_watchlist_board_shape",
        "V18 watchlist board rows validate no-AI multi-market fields",
        started,
        metadata={"symbols": sorted(EXPECTED_SYMBOL_LANES)},
    )


def _run_v17_compatibility_gate(root: Path, python_exe: str) -> LocalWatchlistBoardV18Result:
    started = time.monotonic()
    results = run_local_watchlist_v17_checks(
        project_root=root,
        python_exe=python_exe,
        run_subprocess=False,
    )
    failed = [getattr(result, "check_id", "unknown") for result in results if getattr(result, "status", "") == "failed"]
    metadata = {"checked_results": len(results), "failed_checks": failed}
    if failed:
        return _result(
            "v17_watchlist_compatibility",
            "V17 watchlist gate remains compatible with V18 board",
            started,
            status="failed",
            error="V17 compatibility has failed checks",
            metadata=metadata,
        )
    return _result(
        "v17_watchlist_compatibility",
        "V17 watchlist gate remains compatible with V18 board",
        started,
        metadata=metadata,
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> LocalWatchlistBoardV18Result:
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


def run_local_watchlist_board_v18_checks(
    *,
    project_root: Path = REPO_ROOT,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[LocalWatchlistBoardV18Result]:
    root = project_root.resolve()
    python_path = python_exe or sys.executable
    results: list[LocalWatchlistBoardV18Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_board_shape_check(),
        _run_v17_compatibility_gate(root, python_path),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v18_watchlist_board_unittest",
                title="V18 watchlist board verifier tests pass",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_watchlist_board_v18"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v18_frontend_homepage_watchlist_board_test",
                title="Frontend HomePage V18 watchlist board target test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/pages/__tests__/HomePage.test.tsx",
                    "-t",
                    "watchlist board",
                ],
            )
        )
    return results


def _print_results(results: Sequence[LocalWatchlistBoardV18Result]) -> None:
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA local V18 watchlist board loop.")
    parser.add_argument("--project-root", default=str(REPO_ROOT))
    parser.add_argument("--python", default=sys.executable)
    parser.add_argument("--skip-subprocess", action="store_true")
    parser.add_argument("--json", action="store_true")
    args = parser.parse_args(argv)

    results = run_local_watchlist_board_v18_checks(
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
        print("DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

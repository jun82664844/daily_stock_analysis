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


OK_MARKER = "DSA_PLATFORM_LOCAL_HISTORY_CENTER_V24_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md",
    "scripts/verify_platform_local_history_center_v24.py",
    "tests/test_platform_local_history_center_v24.py",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/components/history/HistoryList.tsx",
    "apps/dsa-web/src/components/history/HistoryListItem.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_history_center_v24.py",
)


@dataclass(frozen=True)
class HistoryCenterV24Result:
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
) -> HistoryCenterV24Result:
    return HistoryCenterV24Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _read_text(root: Path, rel_path: str) -> str:
    path = root / rel_path
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8", errors="replace")


def evaluate_history_center_v24_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    frontend = summary.get("frontend")
    if not isinstance(frontend, Mapping):
        return ["frontend:missing"]

    expected_true = {
        "history_list_connected": "frontend:history_list_missing",
        "filters_rendered": "frontend:filters_missing",
        "market_filter": "frontend:market_filter_missing",
        "code_filter": "frontend:code_filter_missing",
        "report_type_filter": "frontend:report_type_filter_missing",
        "time_filter": "frontend:time_filter_missing",
        "refresh_filter": "frontend:refresh_filter_missing",
        "local_filter_computation": "frontend:local_filtering_missing",
        "refresh_state_session_local": "frontend:refresh_state_missing",
        "refresh_success_gate": "frontend:refresh_success_gate_missing",
        "history_list_controls": "frontend:history_list_controls_missing",
        "item_refresh_badge": "frontend:item_refresh_badge_missing",
        "no_ai_refresh_test": "frontend:no_ai_guard_missing",
    }
    for key, problem in expected_true.items():
        if frontend.get(key) is not True:
            problems.append(problem)
    return problems


def _run_required_files_check(root: Path) -> HistoryCenterV24Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v24_required_files_present",
            "Local History Center V24 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v24_required_files_present",
        "Local History Center V24 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> HistoryCenterV24Result:
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
            "v24_verifiers_visible_to_git",
            "V24 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v24_verifiers_visible_to_git",
        "V24 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_source_shape_check(root: Path) -> HistoryCenterV24Result:
    started = time.monotonic()
    home_page = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    home_test = _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx")
    history_list = _read_text(root, "apps/dsa-web/src/components/history/HistoryList.tsx")
    history_item = _read_text(root, "apps/dsa-web/src/components/history/HistoryListItem.tsx")
    summary = {
        "frontend": {
            "history_list_connected": "HistoryList" in home_page and "<HistoryList" in home_page,
            "filters_rendered": "history-center-filters" in home_page,
            "market_filter": (
                "history-center-market-filter" in home_page
                and ("inferHistoryCenterMarket" in home_page or "toHistoryCenterApiFilters" in home_page)
            ),
            "code_filter": "history-center-code-filter" in home_page and "historyCenterFilters.code" in home_page,
            "report_type_filter": "history-center-report-type-filter" in home_page,
            "time_filter": "history-center-time-filter" in home_page and "history-center-range-filter" in home_page,
            "refresh_filter": "history-center-refresh-filter" in home_page,
            "local_filter_computation": (
                (
                    "const historyCenterItems = useMemo" in home_page
                    and "isWithinHistoryCenterRange" in home_page
                    and "getHistoryCenterTime" in home_page
                )
                or (
                    "setHistoryFilters(toHistoryCenterApiFilters" in home_page
                    and "const historyCenterItems = historyItems" in home_page
                )
            ),
            "refresh_state_session_local": (
                "refreshedHistoryRecordIds" in home_page
                and "setRefreshedHistoryRecordIds" in home_page
                and "refreshedRecordIds={refreshedHistoryRecordIds}" in home_page
            ),
            "refresh_success_gate": (
                "const refreshed = await handleBasicQuery(" in home_page
                and ("if (refreshed)" in home_page or "if (refreshed &&" in home_page)
                and "markHistoryRecordRefreshed(selectedReport.meta.id)" in home_page
            ),
            "history_list_controls": (
                "controls?: React.ReactNode" in history_list
                and "selectable?: boolean" in history_list
                and "refreshedRecordIds?: Set<number>" in history_list
            ),
            "item_refresh_badge": (
                "history-card-refresh-status" in history_item
                and "Current quote refreshed" in history_item
                and "Not refreshed" in history_item
            ),
            "no_ai_refresh_test": (
                "filters the history center" in home_test
                and "stocksApi.snapshot).toHaveBeenCalledWith('AAPL', { refresh: true })" in home_test
                and "analysisApi.analyzeAsync).not.toHaveBeenCalled" in home_test
            ),
        }
    }
    problems = evaluate_history_center_v24_summary(summary)
    if problems:
        return _result(
            "v24_source_shape",
            "V24 history center filters and refresh markers remain wired",
            started,
            status="failed",
            error="source shape does not satisfy V24 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v24_source_shape",
        "V24 history center filters and refresh markers remain wired",
        started,
        metadata={"summary": summary},
    )


def _run_docs_safety_check(root: Path) -> HistoryCenterV24Result:
    started = time.monotonic()
    plan_path = root / "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md"
    if not plan_path.exists():
        return _result(
            "v24_docs_safety",
            "V24 docs keep local-only history-center boundaries",
            started,
            status="failed",
            error="V24 plan document is missing",
        )
    text = plan_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    requirements = {
        "marker": OK_MARKER in text,
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "not_investment_advice": "not investment advice" in lower,
        "no_real_api_key": "do not commit real api key" in lower,
        "no_delete_data": "do not delete history reports" in lower,
        "history_center": "history center" in lower,
        "filters": "market/code/report type/time/refresh" in lower,
        "session_marker": "session-only" in lower,
        "no_ai_refresh": "no-ai" in lower and "current quote" in lower,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v24_docs_safety",
            "V24 docs keep local-only history-center boundaries",
            started,
            status="failed",
            error="V24 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v24_docs_safety",
        "V24 docs keep local-only history-center boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> HistoryCenterV24Result:
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
        return _result(check_id, title, started, status="failed", error="subprocess check failed", metadata=metadata)
    return _result(check_id, title, started, metadata=metadata)


def run_local_history_center_v24_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[HistoryCenterV24Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[HistoryCenterV24Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v24_history_center_unittest",
                title="V24 history center verifier unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_history_center_v24"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v24_frontend_history_center_test",
                title="Frontend history center filter and refresh-marker test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/pages/__tests__/HomePage.test.tsx",
                    "-t",
                    "filters the history center",
                ],
            )
        )
    return results


def _passed_for_marker(results: Sequence[HistoryCenterV24Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[HistoryCenterV24Result]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title} ({result.elapsed_sec:.2f}s)")
        if result.error:
            print(f"     error: {result.error}")
        if result.metadata:
            print(f"     metadata: {json.dumps(result.metadata, ensure_ascii=False, sort_keys=True)}")
    if _passed_for_marker(results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA Local History Center V24 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_history_center_v24_checks(
        project_root=args.project_root,
        python_exe=args.python_exe,
        run_subprocess=not args.skip_subprocess,
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

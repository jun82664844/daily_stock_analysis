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


OK_MARKER = "DSA_PLATFORM_LOCAL_HISTORY_CENTER_V25_OK"

PLAN_DOC = "docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md"

REQUIRED_FILES = (
    PLAN_DOC,
    "scripts/verify_platform_local_history_center_v25.py",
    "tests/test_platform_local_history_center_v25.py",
    "api/v1/endpoints/history.py",
    "api/v1/schemas/history.py",
    "src/services/history_service.py",
    "src/storage.py",
    "apps/dsa-web/src/api/history.ts",
    "apps/dsa-web/src/types/analysis.ts",
    "apps/dsa-web/src/stores/stockPoolStore.ts",
    "apps/dsa-web/src/hooks/useHomeDashboardState.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/components/history/HistoryList.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_history_center_v25.py",
)


@dataclass(frozen=True)
class HistoryCenterV25Result:
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
) -> HistoryCenterV25Result:
    return HistoryCenterV25Result(
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


def evaluate_history_center_v25_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    backend = summary.get("backend")
    frontend = summary.get("frontend")
    if not isinstance(backend, Mapping):
        problems.append("backend:missing")
    if not isinstance(frontend, Mapping):
        problems.append("frontend:missing")
    if problems:
        return problems

    backend_expected = {
        "refresh_marker_table": "backend:refresh_marker_table_missing",
        "market_filter": "backend:market_filter_missing",
        "refresh_status_filter": "backend:refresh_status_filter_missing",
        "stable_sort": "backend:sort_missing",
        "marker_endpoint": "backend:marker_endpoint_missing",
        "user_scoped_marker": "backend:user_scope_missing",
        "no_ai_marker_rejects_ai": "backend:no_ai_guard_missing",
        "backend_test": "backend:test_missing",
    }
    frontend_expected = {
        "history_api_filters": "frontend:history_api_filters_missing",
        "marker_api": "frontend:marker_api_missing",
        "store_history_filters": "frontend:store_filters_missing",
        "home_filter_mapping": "frontend:filter_mapping_missing",
        "home_marker_write": "frontend:marker_write_missing",
        "persistent_badge": "frontend:persistent_badge_missing",
        "frontend_test": "frontend:test_missing",
    }
    for key, problem in backend_expected.items():
        if backend.get(key) is not True:
            problems.append(problem)
    for key, problem in frontend_expected.items():
        if frontend.get(key) is not True:
            problems.append(problem)
    return problems


def _run_required_files_check(root: Path) -> HistoryCenterV25Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v25_required_files_present",
            "Local History Center V25 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v25_required_files_present",
        "Local History Center V25 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> HistoryCenterV25Result:
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
            "v25_verifiers_visible_to_git",
            "V25 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v25_verifiers_visible_to_git",
        "V25 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_source_shape_check(root: Path) -> HistoryCenterV25Result:
    started = time.monotonic()
    storage = _read_text(root, "src/storage.py")
    service = _read_text(root, "src/services/history_service.py")
    endpoint = _read_text(root, "api/v1/endpoints/history.py")
    schema = _read_text(root, "api/v1/schemas/history.py")
    api = _read_text(root, "apps/dsa-web/src/api/history.ts")
    types = _read_text(root, "apps/dsa-web/src/types/analysis.ts")
    store = _read_text(root, "apps/dsa-web/src/stores/stockPoolStore.ts")
    hook = _read_text(root, "apps/dsa-web/src/hooks/useHomeDashboardState.ts")
    home = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    home_test = _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx")
    history_list = _read_text(root, "apps/dsa-web/src/components/history/HistoryList.tsx")
    backend_test = _read_text(root, "tests/test_platform_local_history_center_v25.py")

    summary = {
        "backend": {
            "refresh_marker_table": "class AnalysisHistoryRefreshMarker" in storage,
            "market_filter": "_analysis_history_market_condition" in storage and "market=market" in service,
            "refresh_status_filter": "_analysis_history_refresh_condition" in storage and "refresh_status=refresh_status" in service,
            "stable_sort": "_analysis_history_order_by" in storage and "created_at.asc()" in storage,
            "marker_endpoint": "/{record_id}/refresh-marker" in endpoint,
            "user_scoped_marker": "platform_user_id=_request_history_platform_user_id" in endpoint,
            "no_ai_marker_rejects_ai": "if request.ai_used" in endpoint and "status_code=400" in endpoint,
            "backend_test": "refresh_status=refreshed" in backend_test and "market=crypto" in backend_test,
        },
        "frontend": {
            "history_api_filters": "refresh_status" in api and "queryParams.market" in api,
            "marker_api": "markCurrentQuoteRefreshed" in api and "/refresh-marker" in api,
            "store_history_filters": "historyFilters" in store and "setHistoryFilters" in store,
            "home_filter_mapping": "toHistoryCenterApiFilters" in home and "setHistoryFilters(toHistoryCenterApiFilters" in home,
            "home_marker_write": "historyApi.markCurrentQuoteRefreshed" in home and "stocksApi.snapshot(target, { refresh: true })" in home,
            "persistent_badge": "Boolean(item.currentQuoteRefreshed)" in history_list and "currentQuoteRefreshed" in types,
            "frontend_test": "markCurrentQuoteRefreshed).toHaveBeenCalledWith" in home_test,
            "hook_exposes_filters": "setHistoryFilters: state.setHistoryFilters" in hook,
        },
    }
    problems = evaluate_history_center_v25_summary(summary)
    if problems:
        return _result(
            "v25_source_shape",
            "V25 backend-filtered history center and persistent markers are wired",
            started,
            status="failed",
            error="source shape does not satisfy V25 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v25_source_shape",
        "V25 backend-filtered history center and persistent markers are wired",
        started,
        metadata={"summary": summary},
    )


def _run_docs_safety_check(root: Path) -> HistoryCenterV25Result:
    started = time.monotonic()
    plan_path = root / PLAN_DOC
    if not plan_path.exists():
        return _result(
            "v25_docs_safety",
            "V25 docs keep local-only history-center boundaries",
            started,
            status="failed",
            error="V25 plan document is missing",
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
        "backend_filter": "backend filtering" in lower,
        "persistent_marker": "persistent refresh marker" in lower,
        "no_ai_refresh": "no-ai" in lower and "current quote" in lower,
        "old_report_boundary": "does not rewrite old ai reports" in lower,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v25_docs_safety",
            "V25 docs keep local-only history-center boundaries",
            started,
            status="failed",
            error="V25 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v25_docs_safety",
        "V25 docs keep local-only history-center boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> HistoryCenterV25Result:
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


def run_local_history_center_v25_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[HistoryCenterV25Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[HistoryCenterV25Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v25_history_center_unittest",
                title="V25 history center backend and verifier unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_history_center_v25"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v25_frontend_history_center_test",
                title="Frontend history center backend-filter and refresh-marker test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "run",
                    "test",
                    "--",
                    "HomePage.test.tsx",
                    "-t",
                    "filters the history center",
                ],
            )
        )
    return results


def _passed_for_marker(results: Sequence[HistoryCenterV25Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[HistoryCenterV25Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA Local History Center V25 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_history_center_v25_checks(
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

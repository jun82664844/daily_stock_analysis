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


OK_MARKER = "DSA_PLATFORM_LOCAL_HISTORY_CENTER_V26_OK"
PLAN_DOC = "docs/superpowers/plans/2026-07-03-dsa-local-v26-history-center-usability.md"

REQUIRED_FILES = (
    PLAN_DOC,
    "scripts/verify_platform_local_history_center_v26.py",
    "tests/test_platform_local_history_center_v26.py",
    "apps/dsa-web/src/components/history/HistoryList.tsx",
    "apps/dsa-web/src/hooks/useHomeDashboardState.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/stores/stockPoolStore.ts",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_history_center_v26.py",
)


@dataclass(frozen=True)
class HistoryCenterV26Result:
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
) -> HistoryCenterV26Result:
    return HistoryCenterV26Result(
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


def evaluate_history_center_v26_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    frontend = summary.get("frontend")
    docs = summary.get("docs")
    if not isinstance(frontend, Mapping):
        problems.append("frontend:missing")
    if not isinstance(docs, Mapping):
        problems.append("docs:missing")
    if problems:
        return problems

    frontend_expected = {
        "storage_key": "frontend:storage_key_missing",
        "safe_storage_read": "frontend:safe_storage_read_missing",
        "safe_storage_write": "frontend:safe_storage_write_missing",
        "restored_filters_applied": "frontend:restored_filters_applied_missing",
        "backend_total_in_store": "frontend:backend_total_in_store_missing",
        "history_list_total_count": "frontend:history_list_total_count_missing",
        "frontend_test": "frontend:test_missing",
    }
    docs_expected = {
        "local_only": "docs:local_only_missing",
        "no_real_payment": "docs:no_real_payment_missing",
        "not_investment_advice": "docs:not_investment_advice_missing",
    }

    for key, problem in frontend_expected.items():
        if frontend.get(key) is not True:
            problems.append(problem)
    for key, problem in docs_expected.items():
        if docs.get(key) is not True:
            problems.append(problem)
    return problems


def _run_required_files_check(root: Path) -> HistoryCenterV26Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v26_required_files_present",
            "Local History Center V26 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v26_required_files_present",
        "Local History Center V26 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> HistoryCenterV26Result:
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
            "v26_verifiers_visible_to_git",
            "V26 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v26_verifiers_visible_to_git",
        "V26 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_source_shape_check(root: Path) -> HistoryCenterV26Result:
    started = time.monotonic()
    home = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    home_test = _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx")
    store = _read_text(root, "apps/dsa-web/src/stores/stockPoolStore.ts")
    hook = _read_text(root, "apps/dsa-web/src/hooks/useHomeDashboardState.ts")
    history_list = _read_text(root, "apps/dsa-web/src/components/history/HistoryList.tsx")

    summary = {
        "frontend": {
            "storage_key": "dsa-history-center-filters-v1" in home,
            "safe_storage_read": "readStoredHistoryCenterFilters" in home
            and "normalizeStoredHistoryCenterFilters" in home
            and "JSON.parse(stored)" in home
            and "catch" in home,
            "safe_storage_write": "persistHistoryCenterFilters" in home
            and "localStorage.setItem" in home
            and "JSON.stringify(filters)" in home,
            "restored_filters_applied": "restoredHistoryCenterFiltersRef" in home
            and "setHistoryFilters(toHistoryCenterApiFilters(historyCenterFilters))" in home,
            "backend_total_in_store": "historyTotal" in store
            and "response.total" in store
            and "historyTotal: state.historyTotal" in hook,
            "history_list_total_count": "totalCount" in history_list
            and "history-total-count" in history_list
            and "totalCount={historyTotal}" in home,
            "frontend_test": "restores history center filters from local storage" in home_test
            and "history-total-count" in home_test,
        },
        "docs": _read_docs_summary(root),
    }
    problems = evaluate_history_center_v26_summary(summary)
    if problems:
        return _result(
            "v26_source_shape",
            "V26 history center filter persistence and total count are wired",
            started,
            status="failed",
            error="source shape does not satisfy V26 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v26_source_shape",
        "V26 history center filter persistence and total count are wired",
        started,
        metadata={"summary": summary},
    )


def _read_docs_summary(root: Path) -> dict[str, bool]:
    text = _read_text(root, PLAN_DOC)
    lower = text.lower()
    return {
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "not_investment_advice": "not investment advice" in lower,
    }


def _run_docs_safety_check(root: Path) -> HistoryCenterV26Result:
    started = time.monotonic()
    text = _read_text(root, PLAN_DOC)
    if not text:
        return _result(
            "v26_docs_safety",
            "V26 docs keep local-only history-center boundaries",
            started,
            status="failed",
            error="V26 plan document is missing",
        )
    lower = text.lower()
    requirements = {
        "marker": OK_MARKER in text,
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "not_investment_advice": "not investment advice" in lower,
        "no_real_api_key": "do not commit real api key" in lower,
        "no_delete_data": "do not delete history reports" in lower,
        "local_storage": "localstorage" in lower,
        "safe_validation": "safe validation" in lower or "validated" in lower,
        "backend_total": "backend total" in lower,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v26_docs_safety",
            "V26 docs keep local-only history-center boundaries",
            started,
            status="failed",
            error="V26 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v26_docs_safety",
        "V26 docs keep local-only history-center boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> HistoryCenterV26Result:
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


def run_local_history_center_v26_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[HistoryCenterV26Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[HistoryCenterV26Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v26_history_center_unittest",
                title="V26 history center verifier unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_history_center_v26"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v26_frontend_history_center_test",
                title="Frontend history center filter persistence test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "run",
                    "test",
                    "--",
                    "HomePage.test.tsx",
                    "-t",
                    "restores history center filters",
                ],
            )
        )
    return results


def _passed_for_marker(results: Sequence[HistoryCenterV26Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[HistoryCenterV26Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA Local History Center V26 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_history_center_v26_checks(
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

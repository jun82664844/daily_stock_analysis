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


OK_MARKER = "DSA_PLATFORM_LOCAL_HISTORY_SNAPSHOT_BOUNDARY_V23_OK"

REQUIRED_FILES = (
    "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md",
    "scripts/verify_platform_local_history_snapshot_boundary_v23.py",
    "tests/test_platform_local_history_snapshot_boundary_v23.py",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/api/stocks.ts",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_history_snapshot_boundary_v23.py",
)


@dataclass(frozen=True)
class HistorySnapshotBoundaryV23Result:
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
) -> HistorySnapshotBoundaryV23Result:
    return HistorySnapshotBoundaryV23Result(
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


def evaluate_history_snapshot_boundary_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    frontend = summary.get("frontend")
    if not isinstance(frontend, Mapping):
        return ["frontend:missing"]

    expected_true = {
        "boundary_visible": "frontend:boundary_missing",
        "boundary_copy_marks_historical": "frontend:historical_copy_missing",
        "boundary_copy_marks_not_current": "frontend:not_current_copy_missing",
        "refresh_button_visible": "frontend:refresh_button_missing",
        "refresh_uses_force_snapshot": "frontend:force_snapshot_refresh_missing",
        "refresh_does_not_submit_ai": "frontend:ai_guard_missing",
        "snapshot_branch_preempts_history": "frontend:snapshot_precedence_missing",
    }
    for key, problem in expected_true.items():
        if frontend.get(key) is not True:
            problems.append(problem)
    return problems


def _run_required_files_check(root: Path) -> HistorySnapshotBoundaryV23Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v23_required_files_present",
            "Local History Snapshot Boundary V23 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v23_required_files_present",
        "Local History Snapshot Boundary V23 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> HistorySnapshotBoundaryV23Result:
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
            "v23_verifiers_visible_to_git",
            "V23 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v23_verifiers_visible_to_git",
        "V23 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_source_shape_check(root: Path) -> HistorySnapshotBoundaryV23Result:
    started = time.monotonic()
    home_page = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    home_test = _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx")
    refresh_handler_wired = (
        "handleBasicQuery(selectedReport.meta.stockCode, selectedReport.meta.stockName || undefined, true)"
        in home_page
        or (
            "handleRefreshCurrentQuoteFromHistory" in home_page
            and "const refreshed = await handleBasicQuery(" in home_page
            and "markHistoryRecordRefreshed(selectedReport.meta.id)" in home_page
        )
    )
    summary = {
        "frontend": {
            "boundary_visible": "history-report-freshness-boundary" in home_page,
            "boundary_copy_marks_historical": "Historical AI report" in home_page,
            "boundary_copy_marks_not_current": "not current quote" in home_page,
            "refresh_button_visible": "history-report-refresh-current" in home_page,
            "refresh_uses_force_snapshot": (
                refresh_handler_wired
                and "stocksApi.snapshot).toHaveBeenCalledWith('600519', { refresh: true })" in home_test
            ),
            "refresh_does_not_submit_ai": "analysisApi.analyzeAsync).not.toHaveBeenCalled" in home_test,
            "snapshot_branch_preempts_history": (
                "basicSnapshot && !marketReviewReport" in home_page
                and "!basicSnapshot && selectedReport" in home_page
            ),
        }
    }
    problems = evaluate_history_snapshot_boundary_summary(summary)
    if problems:
        return _result(
            "v23_source_shape",
            "V23 history/current snapshot boundary remains wired",
            started,
            status="failed",
            error="source shape does not satisfy V23 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v23_source_shape",
        "V23 history/current snapshot boundary remains wired",
        started,
        metadata={"summary": summary},
    )


def _run_docs_safety_check(root: Path) -> HistorySnapshotBoundaryV23Result:
    started = time.monotonic()
    plan_path = root / "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md"
    if not plan_path.exists():
        return _result(
            "v23_docs_safety",
            "V23 docs keep local-only and history/current boundaries",
            started,
            status="failed",
            error="V23 plan document is missing",
        )
    text = plan_path.read_text(encoding="utf-8", errors="replace")
    lower = text.lower()
    requirements = {
        "marker": OK_MARKER in text,
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "not_investment_advice": "not investment advice" in lower,
        "no_real_api_key": "do not commit real api key" in lower,
        "history_report": "historical ai report" in lower,
        "current_quote": "current quote" in lower,
        "no_ai_refresh": "no-ai" in lower and "snapshot?refresh=true" in lower,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v23_docs_safety",
            "V23 docs keep local-only and history/current boundaries",
            started,
            status="failed",
            error="V23 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v23_docs_safety",
        "V23 docs keep local-only and history/current boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> HistorySnapshotBoundaryV23Result:
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


def run_local_history_snapshot_boundary_v23_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[HistorySnapshotBoundaryV23Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[HistorySnapshotBoundaryV23Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v23_history_snapshot_boundary_unittest",
                title="V23 history snapshot boundary unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_history_snapshot_boundary_v23"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v23_frontend_history_boundary_test",
                title="Frontend history/current snapshot boundary test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "test",
                    "--",
                    "--run",
                    "src/pages/__tests__/HomePage.test.tsx",
                    "-t",
                    "marks historical reports",
                ],
            )
        )
    return results


def _passed_for_marker(results: Sequence[HistorySnapshotBoundaryV23Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[HistorySnapshotBoundaryV23Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA Local History Snapshot Boundary V23 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_history_snapshot_boundary_v23_checks(
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

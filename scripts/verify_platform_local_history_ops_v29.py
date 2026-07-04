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


OK_MARKER = "DSA_PLATFORM_LOCAL_HISTORY_OPS_V29_OK"
PLAN_DOC = "docs/superpowers/plans/2026-07-04-dsa-local-v29-history-ops.md"

REQUIRED_FILES = (
    PLAN_DOC,
    "scripts/verify_platform_local_history_ops_v29.py",
    "tests/test_platform_local_history_ops_v29.py",
    "src/storage.py",
    "src/services/history_service.py",
    "api/v1/endpoints/history.py",
    "apps/dsa-web/src/api/history.ts",
    "apps/dsa-web/src/types/analysis.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/components/history/HistoryList.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_history_ops_v29.py",
)


@dataclass(frozen=True)
class HistoryOpsV29Result:
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
) -> HistoryOpsV29Result:
    return HistoryOpsV29Result(
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


def evaluate_history_ops_v29_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    expected_groups = {
        "backend": {
            "note_search": "backend:note_search_missing",
            "owner_scoped": "backend:owner_scope_missing",
            "batch_flags": "backend:batch_flags_missing",
            "no_ai": "backend:no_ai_missing",
            "backend_test": "backend:test_missing",
        },
        "frontend": {
            "active_default": "frontend:active_default_missing",
            "note_search_input": "frontend:note_search_input_missing",
            "date_groups": "frontend:date_groups_missing",
            "batch_important_read": "frontend:batch_important_read_missing",
            "frontend_test": "frontend:test_missing",
        },
        "docs": {
            "local_only": "docs:local_only_missing",
            "no_real_payment": "docs:no_real_payment_missing",
            "no_real_api_key": "docs:no_real_api_key_missing",
            "no_delete_data": "docs:no_delete_data_missing",
            "not_investment_advice": "docs:not_investment_advice_missing",
        },
    }

    for group, group_expected in expected_groups.items():
        values = summary.get(group)
        if not isinstance(values, Mapping):
            problems.append(f"{group}:missing")
            continue
        for key, problem in group_expected.items():
            if values.get(key) is not True:
                problems.append(problem)
    return problems


def _run_required_files_check(root: Path) -> HistoryOpsV29Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v29_required_files_present",
            "Local History Ops V29 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v29_required_files_present",
        "Local History Ops V29 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> HistoryOpsV29Result:
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
            "v29_verifiers_visible_to_git",
            "V29 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v29_verifiers_visible_to_git",
        "V29 verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _read_docs_summary(root: Path) -> dict[str, bool]:
    text = _read_text(root, PLAN_DOC)
    lower = text.lower()
    return {
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "no_real_api_key": "do not commit real api key" in lower,
        "no_delete_data": "do not delete history reports" in lower,
        "not_investment_advice": "not investment advice" in lower,
    }


def _run_source_shape_check(root: Path) -> HistoryOpsV29Result:
    started = time.monotonic()
    storage = _read_text(root, "src/storage.py")
    service = _read_text(root, "src/services/history_service.py")
    endpoint = _read_text(root, "api/v1/endpoints/history.py")
    backend_test = _read_text(root, "tests/test_platform_local_history_ops_v29.py")
    history_api = _read_text(root, "apps/dsa-web/src/api/history.ts")
    types = _read_text(root, "apps/dsa-web/src/types/analysis.ts")
    home = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    home_test = _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx")
    history_list = _read_text(root, "apps/dsa-web/src/components/history/HistoryList.tsx")

    summary = {
        "backend": {
            "note_search": "note_search" in endpoint
            and "note_search" in service
            and "_analysis_history_note_search_condition" in storage,
            "owner_scoped": "platform_user_id=platform_user_id" in service + storage
            and "AnalysisHistoryUserState.platform_user_id" in storage,
            "batch_flags": "important" in backend_test
            and "read" in backend_test
            and "batch_response" in backend_test,
            "no_ai": "ai_used=False" in endpoint
            and "ai_used" in backend_test
            and ("without_ai" in backend_test or "no-AI" in backend_test),
            "backend_test": "owner_scoped_note_search" in backend_test
            or "owner_scoped_note_search_and_batch_flags_without_ai" in backend_test,
        },
        "frontend": {
            "active_default": "state: 'active'" in home
            and "history-center-state-filter" in home_test,
            "note_search_input": "noteSearch" in types
            and "note_search" in history_api
            and "history-center-note-filter" in home,
            "date_groups": "historyGroupKey" in history_list
            and "history-group-" in history_list,
            "batch_important_read": "history-center-important-selected" in home
            and "history-center-read-selected" in home
            and "batchUpdateState" in home,
            "frontend_test": "enhances history center" in home_test
            and "analysisApi.analyzeAsync" in home_test,
        },
        "docs": _read_docs_summary(root),
    }
    problems = evaluate_history_ops_v29_summary(summary)
    if problems:
        return _result(
            "v29_source_shape",
            "V29 local history operations are wired without AI or cross-user leakage",
            started,
            status="failed",
            error="source shape does not satisfy V29 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v29_source_shape",
        "V29 local history operations are wired without AI or cross-user leakage",
        started,
        metadata={"summary": summary},
    )


def _run_docs_safety_check(root: Path) -> HistoryOpsV29Result:
    started = time.monotonic()
    text = _read_text(root, PLAN_DOC)
    if not text:
        return _result(
            "v29_docs_safety",
            "V29 docs keep local-only history operations boundaries",
            started,
            status="failed",
            error="V29 plan document is missing",
        )
    lower = text.lower()
    requirements = {
        "marker": OK_MARKER in text,
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "not_investment_advice": "not investment advice" in lower,
        "no_real_api_key": "do not commit real api key" in lower,
        "no_delete_data": "do not delete history reports" in lower,
        "no_ai": "no-ai" in lower or "ai used: false" in lower,
        "note_search": "note_search" in lower or "note search" in lower,
        "owner_scope": "owner-scoped" in lower or "owner scoped" in lower,
        "active_default": "default active" in lower
        or "active default" in lower
        or "default to the active" in lower,
        "batch_flags": "batch important" in lower and "batch read" in lower,
        "date_groups": "date group" in lower or "date grouped" in lower,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v29_docs_safety",
            "V29 docs keep local-only history operations boundaries",
            started,
            status="failed",
            error="V29 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v29_docs_safety",
        "V29 docs keep local-only history operations boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> HistoryOpsV29Result:
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


def run_local_history_ops_v29_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[HistoryOpsV29Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[HistoryOpsV29Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v29_history_ops_unittest",
                title="V29 history operations unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_history_ops_v29"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v29_frontend_history_ops_test",
                title="Frontend local history operations test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "run",
                    "test",
                    "--",
                    "HomePage.test.tsx",
                    "-t",
                    "enhances history center",
                ],
            )
        )
    return results


def _passed_for_marker(results: Sequence[HistoryOpsV29Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[HistoryOpsV29Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA Local History Operations V29 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_history_ops_v29_checks(
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

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


OK_MARKER = "DSA_PLATFORM_LOCAL_HISTORY_EXPORT_V27_OK"
PLAN_DOC = "docs/superpowers/plans/2026-07-04-dsa-local-v27-history-export.md"

REQUIRED_FILES = (
    PLAN_DOC,
    "scripts/verify_platform_local_history_export_v27.py",
    "tests/test_platform_local_history_export_v27.py",
    "api/v1/endpoints/history.py",
    "api/v1/schemas/history.py",
    "apps/dsa-web/src/api/history.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
    "apps/dsa-web/src/types/analysis.ts",
    "apps/dsa-web/src/utils/downloadText.ts",
)

VERIFIER_FILES = (
    "scripts/verify_platform_local_history_export_v27.py",
)


@dataclass(frozen=True)
class HistoryExportV27Result:
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
) -> HistoryExportV27Result:
    return HistoryExportV27Result(
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


def evaluate_history_export_v27_summary(summary: Mapping[str, Any] | Any) -> list[str]:
    problems: list[str] = []
    if not isinstance(summary, Mapping):
        return ["summary:missing"]

    expected_groups = {
        "backend": {
            "export_endpoint": "backend:export_endpoint_missing",
            "export_schemas": "backend:export_schemas_missing",
            "owner_scoped": "backend:owner_scope_missing",
            "no_ai": "backend:no_ai_missing",
            "secret_redaction": "backend:secret_redaction_missing",
            "backend_test": "backend:test_missing",
        },
        "frontend": {
            "export_api": "frontend:export_api_missing",
            "download_helper": "frontend:download_helper_missing",
            "selectable_history_center": "frontend:selectable_history_center_missing",
            "export_button": "frontend:export_button_missing",
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


def _run_required_files_check(root: Path) -> HistoryExportV27Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "v27_required_files_present",
            "Local History Export V27 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "v27_required_files_present",
        "Local History Export V27 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> HistoryExportV27Result:
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
            "v27_verifiers_visible_to_git",
            "V27 verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "v27_verifiers_visible_to_git",
        "V27 verifier files are not gitignored",
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


def _run_source_shape_check(root: Path) -> HistoryExportV27Result:
    started = time.monotonic()
    endpoint = _read_text(root, "api/v1/endpoints/history.py")
    schemas = _read_text(root, "api/v1/schemas/history.py")
    backend_test = _read_text(root, "tests/test_platform_local_history_export_v27.py")
    history_api = _read_text(root, "apps/dsa-web/src/api/history.ts")
    home = _read_text(root, "apps/dsa-web/src/pages/HomePage.tsx")
    home_test = _read_text(root, "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx")
    download_helper = _read_text(root, "apps/dsa-web/src/utils/downloadText.ts")

    summary = {
        "backend": {
            "export_endpoint": '"/export"' in endpoint and "def export_history_records" in endpoint,
            "export_schemas": "class HistoryExportRequest" in schemas and "class HistoryExportResponse" in schemas,
            "owner_scoped": "_request_history_platform_user_id(http_request)" in endpoint
            and "platform_user_id=platform_user_id" in endpoint,
            "no_ai": "ai_used=False" in endpoint and '"ai_used": False' in endpoint,
            "secret_redaction": "redact_metadata" in endpoint and "_redact_export_text" in endpoint,
            "backend_test": "owner_scoped_no_ai_bundle" in backend_test and "sk-v27-export-secret" in backend_test,
        },
        "frontend": {
            "export_api": "exportReports" in history_api and "/api/v1/history/export" in history_api,
            "download_helper": "new Blob" in download_helper and "URL.createObjectURL" in download_helper,
            "selectable_history_center": "selectable" in home and "history-center-export-selected" in home,
            "export_button": "handleExportSelectedHistory" in home and "downloadTextFile" in home,
            "frontend_test": "exports selected history reports as a local no-AI markdown bundle" in home_test
            and "history-center-export-selected" in home_test,
        },
        "docs": _read_docs_summary(root),
    }
    problems = evaluate_history_export_v27_summary(summary)
    if problems:
        return _result(
            "v27_source_shape",
            "V27 local history export is wired without AI or secret leakage",
            started,
            status="failed",
            error="source shape does not satisfy V27 requirements",
            metadata={"summary": summary, "problems": problems},
        )
    return _result(
        "v27_source_shape",
        "V27 local history export is wired without AI or secret leakage",
        started,
        metadata={"summary": summary},
    )


def _run_docs_safety_check(root: Path) -> HistoryExportV27Result:
    started = time.monotonic()
    text = _read_text(root, PLAN_DOC)
    if not text:
        return _result(
            "v27_docs_safety",
            "V27 docs keep local-only export boundaries",
            started,
            status="failed",
            error="V27 plan document is missing",
        )
    lower = text.lower()
    requirements = {
        "marker": OK_MARKER in text,
        "local_only": "local-only" in lower or "local only" in lower,
        "no_real_payment": "not real payment" in lower,
        "not_investment_advice": "not investment advice" in lower,
        "no_real_api_key": "do not commit real api key" in lower,
        "no_delete_data": "do not delete history reports" in lower,
        "no_ai_export": "no-ai" in lower or "ai used: false" in lower,
        "secret_redaction": "secret" in lower and "redact" in lower,
        "markdown_json": "markdown" in lower and "json" in lower,
    }
    missing = sorted(label for label, present in requirements.items() if not present)
    if missing:
        return _result(
            "v27_docs_safety",
            "V27 docs keep local-only export boundaries",
            started,
            status="failed",
            error="V27 docs are missing safety copy",
            metadata={"missing": missing},
        )
    return _result(
        "v27_docs_safety",
        "V27 docs keep local-only export boundaries",
        started,
        metadata={"requirements": sorted(requirements)},
    )


def _run_subprocess_check(
    *,
    check_id: str,
    title: str,
    cwd: Path,
    command: Sequence[str],
) -> HistoryExportV27Result:
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


def run_local_history_export_v27_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    run_subprocess: bool = True,
) -> list[HistoryExportV27Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    python_path = python_exe or sys.executable
    results: list[HistoryExportV27Result] = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_source_shape_check(root),
        _run_docs_safety_check(root),
    ]
    if run_subprocess:
        results.append(
            _run_subprocess_check(
                check_id="v27_history_export_unittest",
                title="V27 history export unittest passes",
                cwd=root,
                command=[python_path, "-m", "unittest", "tests.test_platform_local_history_export_v27"],
            )
        )
        results.append(
            _run_subprocess_check(
                check_id="v27_frontend_history_export_test",
                title="Frontend selected history export test passes",
                cwd=root / "apps" / "dsa-web",
                command=[
                    _resolve_executable("npm"),
                    "run",
                    "test",
                    "--",
                    "HomePage.test.tsx",
                    "-t",
                    "exports selected history reports",
                ],
            )
        )
    return results


def _passed_for_marker(results: Sequence[HistoryExportV27Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[HistoryExportV27Result]) -> None:
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
    parser = argparse.ArgumentParser(description="Verify DSA Local History Export V27 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip backend/frontend subprocess checks")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_history_export_v27_checks(
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

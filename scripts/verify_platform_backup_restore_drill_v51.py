from __future__ import annotations

import argparse
import json
import sqlite3
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK"

REQUIRED_FILES = (
    "src/services/platform_backup.py",
    "scripts/run_platform_backup_restore_dry_run.py",
    "tests/test_platform_backup_restore_drill_v51.py",
    "docs/superpowers/plans/2026-07-05-dsa-backup-restore-drill-v51.md",
)

REQUIRED_MARKERS = {
    "src/services/platform_backup.py": (
        "run_sqlite_backup_restore_dry_run",
        "integrity_check",
        "source_unchanged",
        "destructive",
        "ai_used",
    ),
    "scripts/run_platform_backup_restore_dry_run.py": (
        "local/backups/dry-runs",
        "database_required",
        "run_sqlite_backup_restore_dry_run",
    ),
    "docs/superpowers/plans/2026-07-05-dsa-backup-restore-drill-v51.md": (
        "DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK",
        "does not delete",
        "No AI calls",
    ),
}


@dataclass(frozen=True)
class VerifyResult:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
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
    metadata: dict | None = None,
) -> VerifyResult:
    return VerifyResult(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
    )


def _run_required_files_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "V51 backup restore drill files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "V51 backup restore drill files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_static_markers_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    missing: dict[str, list[str]] = {}
    for rel_path, markers in REQUIRED_MARKERS.items():
        path = root / rel_path
        text = path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""
        absent = [marker for marker in markers if marker not in text]
        if absent:
            missing[rel_path] = absent
    if missing:
        return _result(
            "static_markers_present",
            "V51 source markers are present",
            started,
            status="failed",
            error="required markers are missing",
            metadata={"missing_markers": missing},
        )
    return _result(
        "static_markers_present",
        "V51 source markers are present",
        started,
        metadata={"checked_files": sorted(REQUIRED_MARKERS)},
    )


def _create_source_db(path: Path) -> None:
    with sqlite3.connect(path) as conn:
        conn.execute("CREATE TABLE platform_users (id INTEGER PRIMARY KEY, email TEXT NOT NULL)")
        conn.execute("CREATE TABLE analysis_history (id INTEGER PRIMARY KEY, code TEXT NOT NULL)")
        conn.execute("INSERT INTO platform_users(email) VALUES ('v51@example.com')")
        conn.execute("INSERT INTO analysis_history(code) VALUES ('AAPL')")
        conn.commit()


def _run_temp_drill_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
        temp_root = Path(temp_dir)
        source = temp_root / "source.sqlite"
        output_dir = temp_root / "out"
        _create_source_db(source)
        completed = subprocess.run(
            [
                sys.executable,
                "scripts/run_platform_backup_restore_dry_run.py",
                "--database",
                str(source),
                "--output-dir",
                str(output_dir),
                "--label",
                "v51-verifier",
            ],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode != 0:
            return _result(
                "temp_backup_restore_drill",
                "Temporary backup restore drill succeeds",
                started,
                status="failed",
                error="dry-run runner failed",
                metadata={"stdout_tail": completed.stdout[-1000:], "stderr_tail": completed.stderr[-1000:]},
            )
        payload = json.loads(completed.stdout)
        if not payload.get("success") or payload.get("destructive") or payload.get("ai_used"):
            return _result(
                "temp_backup_restore_drill",
                "Temporary backup restore drill succeeds",
                started,
                status="failed",
                error="dry-run payload is unsafe",
                metadata={"payload": payload},
            )
        return _result(
            "temp_backup_restore_drill",
            "Temporary backup restore drill succeeds",
            started,
            metadata={
                "source_unchanged": payload.get("source_unchanged"),
                "row_counts_match": payload.get("row_counts_match"),
                "backup_bytes": payload.get("backup", {}).get("bytes"),
            },
        )


def _run_unittest_check(root: Path) -> VerifyResult:
    started = time.monotonic()
    completed = subprocess.run(
        [sys.executable, "-m", "unittest", "tests.test_platform_backup_restore_drill_v51"],
        cwd=root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if completed.returncode != 0:
        return _result(
            "v51_unittests",
            "V51 backup restore drill tests pass",
            started,
            status="failed",
            error="V51 unittest failed",
            metadata={"stdout_tail": completed.stdout[-800:], "stderr_tail": completed.stderr[-1200:]},
        )
    return _result(
        "v51_unittests",
        "V51 backup restore drill tests pass",
        started,
        metadata={"stderr_tail": completed.stderr[-800:]},
    )


def run_checks(*, project_root: str | Path | None = None) -> list[VerifyResult]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    return [
        _run_required_files_check(root),
        _run_static_markers_check(root),
        _run_temp_drill_check(root),
        _run_unittest_check(root),
    ]


def _print_text_report(results: Sequence[VerifyResult]) -> None:
    for result in results:
        marker = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")
    if all(result.status == "passed" for result in results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA backup restore drill V51 package")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_checks(project_root=args.project_root)
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    else:
        _print_text_report(results)
    return 0 if all(result.status == "passed" for result in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

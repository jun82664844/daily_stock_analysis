# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_local_history_snapshot_boundary_v23 import (
    evaluate_history_snapshot_boundary_summary,
    run_local_history_snapshot_boundary_v23_checks,
)


class PlatformLocalHistorySnapshotBoundaryV23TestCase(unittest.TestCase):
    def test_evaluate_history_snapshot_boundary_summary_accepts_complete_shape(self) -> None:
        summary = {
            "frontend": {
                "boundary_visible": True,
                "boundary_copy_marks_historical": True,
                "boundary_copy_marks_not_current": True,
                "refresh_button_visible": True,
                "refresh_uses_force_snapshot": True,
                "refresh_does_not_submit_ai": True,
                "snapshot_branch_preempts_history": True,
            }
        }

        self.assertEqual(evaluate_history_snapshot_boundary_summary(summary), [])

    def test_evaluate_history_snapshot_boundary_summary_rejects_missing_boundary(self) -> None:
        summary = {
            "frontend": {
                "boundary_visible": False,
                "boundary_copy_marks_historical": True,
                "boundary_copy_marks_not_current": False,
                "refresh_button_visible": False,
                "refresh_uses_force_snapshot": True,
                "refresh_does_not_submit_ai": False,
                "snapshot_branch_preempts_history": True,
            }
        }

        problems = evaluate_history_snapshot_boundary_summary(summary)

        self.assertIn("frontend:boundary_missing", problems)
        self.assertIn("frontend:not_current_copy_missing", problems)
        self.assertIn("frontend:refresh_button_missing", problems)
        self.assertIn("frontend:ai_guard_missing", problems)

    def test_required_files_check_reports_missing_v23_plan(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_local_history_snapshot_boundary_v23_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v23_required_files_present"].status, "failed")
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md",
            by_id["v23_required_files_present"].metadata["missing_files"],
        )


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_local_history_center_v24 import (
    evaluate_history_center_v24_summary,
    run_local_history_center_v24_checks,
)


class PlatformLocalHistoryCenterV24TestCase(unittest.TestCase):
    def test_evaluate_history_center_v24_summary_accepts_complete_shape(self) -> None:
        summary = {
            "frontend": {
                "history_list_connected": True,
                "filters_rendered": True,
                "market_filter": True,
                "code_filter": True,
                "report_type_filter": True,
                "time_filter": True,
                "refresh_filter": True,
                "local_filter_computation": True,
                "refresh_state_session_local": True,
                "refresh_success_gate": True,
                "history_list_controls": True,
                "item_refresh_badge": True,
                "no_ai_refresh_test": True,
            }
        }

        self.assertEqual(evaluate_history_center_v24_summary(summary), [])

    def test_evaluate_history_center_v24_summary_rejects_missing_filters_and_marker(self) -> None:
        summary = {
            "frontend": {
                "history_list_connected": True,
                "filters_rendered": False,
                "market_filter": False,
                "code_filter": True,
                "report_type_filter": False,
                "time_filter": False,
                "refresh_filter": False,
                "local_filter_computation": True,
                "refresh_state_session_local": False,
                "refresh_success_gate": False,
                "history_list_controls": True,
                "item_refresh_badge": False,
                "no_ai_refresh_test": False,
            }
        }

        problems = evaluate_history_center_v24_summary(summary)

        self.assertIn("frontend:filters_missing", problems)
        self.assertIn("frontend:market_filter_missing", problems)
        self.assertIn("frontend:report_type_filter_missing", problems)
        self.assertIn("frontend:time_filter_missing", problems)
        self.assertIn("frontend:refresh_filter_missing", problems)
        self.assertIn("frontend:refresh_state_missing", problems)
        self.assertIn("frontend:refresh_success_gate_missing", problems)
        self.assertIn("frontend:item_refresh_badge_missing", problems)
        self.assertIn("frontend:no_ai_guard_missing", problems)

    def test_required_files_check_reports_missing_v24_plan(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_local_history_center_v24_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v24_required_files_present"].status, "failed")
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md",
            by_id["v24_required_files_present"].metadata["missing_files"],
        )


if __name__ == "__main__":
    unittest.main()

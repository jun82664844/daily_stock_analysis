# -*- coding: utf-8 -*-
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class PlatformLocalQueryWorkspaceV19TestCase(unittest.TestCase):
    def test_v19_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_query_workspace_v19.py"

        self.assertTrue(verifier.exists(), "V19 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_query_workspace_v19"))

        from scripts.verify_platform_local_query_workspace_v19 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK")

    def test_query_workspace_segments_accept_separated_local_query_state(self) -> None:
        from scripts.verify_platform_local_query_workspace_v19 import evaluate_query_workspace_segments

        segments = {
            "current_snapshot": {"ai_used": False, "route_lane": "hk_market_data", "freshness": "fresh"},
            "watchlist": {"private": True, "count": 4},
            "history_reports": {"separate": True, "count": 0},
            "ai_analysis": {"trigger": "manual", "selected_mode": "platform", "quick_snapshot_consumes_ai": False},
        }

        self.assertEqual(evaluate_query_workspace_segments(segments), [])

    def test_query_workspace_segments_reject_mixed_ai_or_history_state(self) -> None:
        from scripts.verify_platform_local_query_workspace_v19 import evaluate_query_workspace_segments

        segments = {
            "current_snapshot": {"ai_used": True, "route_lane": "unknown", "freshness": ""},
            "watchlist": {"private": False, "count": -1},
            "history_reports": {"separate": False, "count": 0},
            "ai_analysis": {"trigger": "auto", "selected_mode": "mystery", "quick_snapshot_consumes_ai": True},
        }

        problems = evaluate_query_workspace_segments(segments)

        self.assertIn("current_snapshot:ai_used_not_false", problems)
        self.assertIn("current_snapshot:route_lane_missing", problems)
        self.assertIn("watchlist:not_private", problems)
        self.assertIn("history_reports:not_separate", problems)
        self.assertIn("ai_analysis:not_manual", problems)
        self.assertIn("ai_analysis:quick_snapshot_consumes_ai", problems)

    def test_v19_required_file_check_can_run_without_subprocess(self) -> None:
        from scripts.verify_platform_local_query_workspace_v19 import REQUIRED_FILES, run_local_query_workspace_v19_checks
        from scripts.verify_platform_local_watchlist_board_v18 import REQUIRED_FILES as V18_REQUIRED_FILES

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            for rel_path in set(REQUIRED_FILES) | set(V18_REQUIRED_FILES):
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8")

            with patch(
                "scripts.verify_platform_local_query_workspace_v19.run_local_watchlist_board_v18_checks",
                return_value=[SimpleNamespace(check_id="v18_stub", status="passed")],
            ):
                results = run_local_query_workspace_v19_checks(
                    project_root=root,
                    python_exe="python",
                    run_subprocess=False,
                )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v19_required_files_present"].status, "passed")
        self.assertEqual(by_id["v19_query_workspace_shape"].status, "passed")
        self.assertEqual(by_id["v18_watchlist_board_compatibility"].status, "passed")


if __name__ == "__main__":
    unittest.main()

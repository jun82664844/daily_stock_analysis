# -*- coding: utf-8 -*-
import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformLocalUserQueryLoopV15TestCase(unittest.TestCase):
    def test_snapshot_payload_accepts_no_ai_market_lanes(self) -> None:
        from scripts.verify_platform_local_user_query_loop_v15 import evaluate_user_query_snapshot_payload

        payload = {
            "stockCode": "HK00700",
            "market": "hk",
            "quote": {"freshness": "fresh", "source": "yahoo_chart"},
            "route": {
                "dataSourceLane": "hk_market_data",
                "channel": "hk_equity",
                "aiRequired": False,
            },
            "diagnostics": {"routeLane": "hk_market_data"},
            "aiUsed": False,
        }

        self.assertEqual(evaluate_user_query_snapshot_payload(payload), [])

    def test_snapshot_payload_rejects_ai_and_secret_like_text(self) -> None:
        from scripts.verify_platform_local_user_query_loop_v15 import evaluate_user_query_snapshot_payload

        payload = {
            "stock_code": "AAPL",
            "market": "us",
            "quote": {"source": "yahoo_chart"},
            "route": {
                "data_source_lane": "unknown_lane",
                "ai_required": True,
            },
            "metadata": {"authorization": "Bearer sk-v15-secret-must-not-leak"},
            "ai_used": True,
        }

        problems = evaluate_user_query_snapshot_payload(payload)

        self.assertIn("ai_used_not_false", problems)
        self.assertIn("unexpected_or_missing_market_lane", problems)
        self.assertIn("route_ai_required_not_false", problems)
        self.assertIn("quote_freshness_missing", problems)
        self.assertIn("secret_like_text_present", problems)

    def test_v15_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_user_query_loop_v15.py"

        self.assertTrue(verifier.exists(), "V15 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_user_query_loop_v15"))

        from scripts.verify_platform_local_user_query_loop_v15 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK")

    def test_v15_required_file_check_can_run_without_live_or_subprocess(self) -> None:
        from scripts.verify_platform_local_user_query_loop_v15 import REQUIRED_FILES, run_local_user_query_loop_v15_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            for rel_path in REQUIRED_FILES:
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8")

            results = run_local_user_query_loop_v15_checks(
                project_root=root,
                python_exe="python",
                run_subprocess=False,
                run_live=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v15_required_files_present"].status, "passed")
        self.assertEqual(by_id["v15_no_ai_market_lane_payload_shape"].status, "passed")


if __name__ == "__main__":
    unittest.main()

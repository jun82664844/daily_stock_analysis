# -*- coding: utf-8 -*-
import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformLocalWatchlistV17VerifierTestCase(unittest.TestCase):
    def test_v17_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_watchlist_v17.py"

        self.assertTrue(verifier.exists(), "V17 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_watchlist_v17"))

        from scripts.verify_platform_local_watchlist_v17 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK")

    def test_watchlist_refresh_summary_accepts_no_ai_market_lanes(self) -> None:
        from scripts.verify_platform_local_watchlist_v17 import evaluate_watchlist_refresh_summary

        summary = {
            "requested": 4,
            "refreshed": 4,
            "degraded": 1,
            "ai_used": False,
            "items": [
                {"stock_code": "600519", "route_lane": "a_share_market_data", "ai_used": False, "status": "ok"},
                {"stock_code": "AAPL", "route_lane": "us_market_data", "ai_used": False, "status": "ok"},
                {"stock_code": "HK00700", "route_lane": "hk_market_data", "ai_used": False, "status": "degraded"},
                {"stock_code": "BTC-USD", "route_lane": "crypto_market_data", "ai_used": False, "status": "ok"},
            ],
        }

        self.assertEqual(evaluate_watchlist_refresh_summary(summary), [])

    def test_watchlist_refresh_summary_rejects_ai_or_wrong_lane(self) -> None:
        from scripts.verify_platform_local_watchlist_v17 import evaluate_watchlist_refresh_summary

        summary = {
            "requested": 2,
            "refreshed": 2,
            "degraded": 0,
            "ai_used": True,
            "items": [
                {"stock_code": "600519", "route_lane": "us_market_data", "ai_used": False, "status": "ok"},
                {"stock_code": "AAPL", "route_lane": "us_market_data", "ai_used": True, "status": "ok"},
            ],
        }

        problems = evaluate_watchlist_refresh_summary(summary)

        self.assertIn("summary:ai_used_not_false", problems)
        self.assertIn("600519:unexpected_lane", problems)
        self.assertIn("AAPL:ai_used_not_false", problems)

    def test_v17_required_file_check_can_run_without_subprocess(self) -> None:
        from scripts.verify_platform_local_watchlist_v17 import REQUIRED_FILES, run_local_watchlist_v17_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            for rel_path in REQUIRED_FILES:
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8")

            results = run_local_watchlist_v17_checks(
                project_root=root,
                python_exe="python",
                run_subprocess=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v17_required_files_present"].status, "passed")
        self.assertEqual(by_id["v17_watchlist_refresh_summary_shape"].status, "passed")


if __name__ == "__main__":
    unittest.main()

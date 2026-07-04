# -*- coding: utf-8 -*-
import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformLocalBrowserUserLoopV16TestCase(unittest.TestCase):
    def test_v16_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_browser_user_loop_v16.py"

        self.assertTrue(verifier.exists(), "V16 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_browser_user_loop_v16"))

        from scripts.verify_platform_local_browser_user_loop_v16 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK")

    def test_multi_market_live_smoke_summary_accepts_no_ai_routes(self) -> None:
        from scripts.verify_platform_local_browser_user_loop_v16 import evaluate_live_browser_smoke_summary

        summary = {
            "600519": {"status_code": 200, "lane": "a_share_market_data", "ai_used": False, "freshness": "fresh"},
            "AAPL": {"status_code": 200, "lane": "us_market_data", "ai_used": False, "freshness": "fresh"},
            "HK00700": {"status_code": 200, "lane": "hk_market_data", "ai_used": False, "freshness": "fresh"},
            "BTC-USD": {"status_code": 200, "lane": "crypto_market_data", "ai_used": False, "freshness": "stale"},
        }

        self.assertEqual(evaluate_live_browser_smoke_summary(summary), [])

    def test_multi_market_live_smoke_summary_rejects_ai_or_wrong_lane(self) -> None:
        from scripts.verify_platform_local_browser_user_loop_v16 import evaluate_live_browser_smoke_summary

        summary = {
            "600519": {"status_code": 200, "lane": "us_market_data", "ai_used": False, "freshness": "fresh"},
            "AAPL": {"status_code": 200, "lane": "us_market_data", "ai_used": True, "freshness": "fresh"},
            "HK00700": {"status_code": 503, "lane": "hk_market_data", "ai_used": False, "freshness": ""},
            "BTC-USD": {"status_code": 200, "lane": "crypto_market_data", "ai_used": False, "freshness": "stale"},
        }

        problems = evaluate_live_browser_smoke_summary(summary)

        self.assertIn("600519:unexpected_lane", problems)
        self.assertIn("AAPL:ai_used_not_false", problems)
        self.assertIn("HK00700:status_not_200", problems)
        self.assertIn("HK00700:freshness_missing", problems)

    def test_v16_required_file_check_can_run_without_live_or_subprocess(self) -> None:
        from scripts.verify_platform_local_browser_user_loop_v16 import REQUIRED_FILES, run_local_browser_user_loop_v16_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            for rel_path in REQUIRED_FILES:
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8")

            results = run_local_browser_user_loop_v16_checks(
                project_root=root,
                python_exe="python",
                run_subprocess=False,
                run_live=False,
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v16_required_files_present"].status, "passed")
        self.assertEqual(by_id["v16_live_smoke_summary_shape"].status, "passed")


if __name__ == "__main__":
    unittest.main()

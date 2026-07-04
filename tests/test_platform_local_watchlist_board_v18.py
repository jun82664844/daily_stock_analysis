# -*- coding: utf-8 -*-
import importlib.util
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch


class PlatformLocalWatchlistBoardV18TestCase(unittest.TestCase):
    def test_v18_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_watchlist_board_v18.py"

        self.assertTrue(verifier.exists(), "V18 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_watchlist_board_v18"))

        from scripts.verify_platform_local_watchlist_board_v18 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK")

    def test_watchlist_board_rows_accept_no_ai_multi_market_fields(self) -> None:
        from scripts.verify_platform_local_watchlist_board_v18 import evaluate_watchlist_board_rows

        rows = [
            {
                "stock_code": "600519",
                "stock_name": "Kweichow Moutai",
                "market": "cn",
                "route_lane": "a_share_market_data",
                "current_price": 1512.34,
                "change_percent": 1.23,
                "freshness": "fresh",
                "degradation_status": "ok",
                "warning_codes": [],
                "ai_used": False,
                "status": "ok",
            },
            {
                "stock_code": "AAPL",
                "stock_name": "Apple Inc.",
                "market": "us",
                "route_lane": "us_market_data",
                "current_price": 211.88,
                "change_percent": -0.42,
                "freshness": "fresh",
                "degradation_status": "ok",
                "warning_codes": [],
                "ai_used": False,
                "status": "ok",
            },
            {
                "stock_code": "HK00700",
                "stock_name": "Tencent Holdings",
                "market": "hk",
                "route_lane": "hk_market_data",
                "current_price": 390.2,
                "change_percent": 0.8,
                "freshness": "fresh",
                "degradation_status": "degraded",
                "warning_codes": ["missing_history"],
                "ai_used": False,
                "status": "degraded",
            },
            {
                "stock_code": "BTC-USD",
                "stock_name": "Bitcoin",
                "market": "crypto",
                "route_lane": "crypto_market_data",
                "current_price": 61888.12,
                "change_percent": 2.5,
                "freshness": "fresh",
                "degradation_status": "ok",
                "warning_codes": [],
                "ai_used": False,
                "status": "ok",
            },
        ]

        self.assertEqual(evaluate_watchlist_board_rows(rows), [])

    def test_watchlist_board_rows_accept_camel_case_frontend_payloads(self) -> None:
        from scripts.verify_platform_local_watchlist_board_v18 import evaluate_watchlist_board_rows

        rows = [
            {
                "stockCode": "600519",
                "stockName": "Kweichow Moutai",
                "market": "cn",
                "routeLane": "a_share_market_data",
                "currentPrice": 1512.34,
                "changePercent": 1.23,
                "freshness": "fresh",
                "degradationStatus": "ok",
                "warningCodes": [],
                "aiUsed": False,
                "status": "ok",
            },
            {
                "stockCode": "AAPL",
                "stockName": "Apple Inc.",
                "market": "us",
                "routeLane": "us_market_data",
                "currentPrice": 211.88,
                "changePercent": -0.42,
                "freshness": "fresh",
                "degradationStatus": "ok",
                "warningCodes": [],
                "aiUsed": False,
                "status": "ok",
            },
            {
                "stockCode": "HK00700",
                "stockName": "Tencent Holdings",
                "market": "hk",
                "routeLane": "hk_market_data",
                "currentPrice": 390.2,
                "changePercent": 0.8,
                "freshness": "fresh",
                "degradationStatus": "degraded",
                "warningCodes": ["missing_history"],
                "aiUsed": False,
                "status": "degraded",
            },
            {
                "stockCode": "BTC-USD",
                "stockName": "Bitcoin",
                "market": "crypto",
                "routeLane": "crypto_market_data",
                "currentPrice": 61888.12,
                "changePercent": 2.5,
                "freshness": "fresh",
                "degradationStatus": "ok",
                "warningCodes": [],
                "aiUsed": False,
                "status": "ok",
            },
        ]

        self.assertEqual(evaluate_watchlist_board_rows(rows), [])

    def test_watchlist_board_rows_reject_ai_missing_price_or_wrong_lane(self) -> None:
        from scripts.verify_platform_local_watchlist_board_v18 import evaluate_watchlist_board_rows

        rows = [
            {
                "stock_code": "600519",
                "stock_name": "Kweichow Moutai",
                "market": "cn",
                "route_lane": "us_market_data",
                "current_price": None,
                "change_percent": 1.23,
                "freshness": "fresh",
                "degradation_status": "ok",
                "ai_used": True,
                "status": "ok",
            }
        ]

        problems = evaluate_watchlist_board_rows(rows)

        self.assertIn("600519:unexpected_lane", problems)
        self.assertIn("600519:price_missing", problems)
        self.assertIn("600519:ai_used_not_false", problems)
        self.assertIn("AAPL:missing", problems)

    def test_v18_required_file_check_can_run_without_subprocess(self) -> None:
        from scripts.verify_platform_local_watchlist_board_v18 import REQUIRED_FILES, run_local_watchlist_board_v18_checks
        from scripts.verify_platform_local_watchlist_v17 import REQUIRED_FILES as V17_REQUIRED_FILES

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            for rel_path in set(REQUIRED_FILES) | set(V17_REQUIRED_FILES):
                path = root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("ok\n", encoding="utf-8")

            with patch(
                "scripts.verify_platform_local_watchlist_board_v18.run_local_watchlist_v17_checks",
                return_value=[SimpleNamespace(check_id="v17_stub", status="passed")],
            ):
                results = run_local_watchlist_board_v18_checks(
                    project_root=root,
                    python_exe="python",
                    run_subprocess=False,
                )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v18_required_files_present"].status, "passed")
        self.assertEqual(by_id["v18_watchlist_board_shape"].status, "passed")
        self.assertEqual(by_id["v17_watchlist_compatibility"].status, "passed")


if __name__ == "__main__":
    unittest.main()

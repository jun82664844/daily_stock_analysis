from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


class FakeKronosStockService:
    def get_realtime_quote(self, stock_code: str):
        return {
            "stock_code": stock_code,
            "stock_name": "Apple Inc.",
            "current_price": 200.0,
            "change_percent": 1.5,
            "open": 198.0,
            "high": 205.0,
            "low": 197.0,
            "prev_close": 197.0,
            "volume": 1200000,
            "amount": 240000000,
            "source": "unit_quote",
            "freshness": "fresh",
        }

    def get_history_data(self, stock_code: str, **_kwargs):
        return {
            "stock_code": stock_code,
            "stock_name": "Apple Inc.",
            "source": "unit_history",
            "data": [
                {
                    "date": f"2026-06-{day:02d}",
                    "open": 178.0 + day,
                    "high": 181.0 + day,
                    "low": 176.0 + day,
                    "close": 180.0 + day,
                    "volume": 1000 + day * 10,
                    "amount": 200000 + day * 1000,
                }
                for day in range(1, 22)
            ],
        }


class KronosForecastServiceV58TestCase(unittest.TestCase):
    def test_forecast_is_explicitly_unavailable_without_runtime_dependencies(self) -> None:
        from src.services.kronos_forecast_service import KronosForecastService

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            record_path = Path(temp_dir) / "kronos.jsonl"
            with patch.dict("os.environ", {"KRONOS_ENABLED": "true", "KRONOS_RECORD_PATH": str(record_path)}):
                service = KronosForecastService(
                    stock_service=FakeKronosStockService(),
                    dependency_probe=lambda: {
                        "pandas": True,
                        "torch": False,
                        "transformers": False,
                        "huggingface_hub": True,
                        "model": False,
                    },
                )
                result = service.forecast("AAPL", lookback=20, horizon=5)
                serialized = record_path.read_text(encoding="utf-8")

            self.assertEqual(result["status"], "model_unavailable")
            self.assertEqual(result["source"], "local_kline_rules_kronos_unavailable")
            self.assertFalse(result["ai_used"])
            self.assertFalse(result["public_search_used"])
            self.assertFalse(result["kronos_model_used"])
            self.assertIn("torch", result["missing_dependencies"])
            self.assertIn("model", result["missing_dependencies"])
            self.assertEqual(result["horizon"], "next_5_bars")
            self.assertGreaterEqual(len(result["scenarios"]), 3)
            self.assertGreaterEqual(len(result["forecast_points"]), 5)
            self.assertIn("not investment advice", result["boundary"])
            self.assertTrue(result["record_id"])
            self.assertTrue(record_path.exists())
            self.assertIn("model_unavailable", serialized)

    def test_forecast_cache_and_backtest_summary_are_secret_free(self) -> None:
        from src.services.kronos_forecast_service import KronosForecastService

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            record_path = Path(temp_dir) / "kronos.jsonl"
            with patch.dict("os.environ", {"KRONOS_ENABLED": "false", "KRONOS_RECORD_PATH": str(record_path)}):
                service = KronosForecastService(
                    stock_service=FakeKronosStockService(),
                    dependency_probe=lambda: {
                        "pandas": True,
                        "torch": False,
                        "transformers": False,
                        "huggingface_hub": True,
                        "model": False,
                    },
                )
                first = service.forecast("AAPL", lookback=20, horizon=5)
                second = service.forecast("AAPL", lookback=20, horizon=5)
                serialized = record_path.read_text(encoding="utf-8")

            self.assertFalse(first["cache_hit"])
            self.assertTrue(second["cache_hit"])
            self.assertEqual(second["backtest_summary"]["records"], 1)
            self.assertNotIn("sk-", serialized.lower())
            self.assertNotIn("api_key", serialized.lower())


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import tempfile
import time
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


class SlowHistoryKronosStockService(FakeKronosStockService):
    def get_history_data(self, stock_code: str, **_kwargs):
        time.sleep(1.0)
        return super().get_history_data(stock_code, **_kwargs)


class KronosForecastServiceV58TestCase(unittest.TestCase):
    def test_enabled_runtime_requires_explicit_model_permission(self) -> None:
        from src.services.kronos_forecast_service import KronosForecastService

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "KRONOS_ENABLED": "true",
                    "KRONOS_RECORD_PATH": str(Path(temp_dir) / "kronos.jsonl"),
                },
            ):
                service = KronosForecastService(
                    stock_service=FakeKronosStockService(),
                    dependency_probe=lambda: {
                        "pandas": True,
                        "torch": True,
                        "einops": True,
                        "safetensors": True,
                        "huggingface_hub": True,
                        "model": True,
                    },
                )
                with patch.object(service, "_run_kronos_model") as run_model:
                    result = service.forecast("AAPL", lookback=20, horizon=5, allow_model=False)

        run_model.assert_not_called()
        self.assertEqual(result["status"], "premium_required")
        self.assertFalse(result["kronos_model_used"])
        self.assertEqual(result["runtime_metrics"]["model_cache_hit"], False)

    def test_successful_real_model_run_exposes_runtime_metrics(self) -> None:
        from src.services.kronos_forecast_service import KronosForecastService

        model_result = {
            "points": [
                {
                    "timestamp": f"2026-07-{day:02d}",
                    "open": 200.0 + day,
                    "high": 202.0 + day,
                    "low": 199.0 + day,
                    "close": 201.0 + day,
                    "volume": 1000.0,
                    "amount": 200000.0,
                }
                for day in range(1, 6)
            ],
            "metrics": {
                "resolved_device": "cuda",
                "model_cache_hit": False,
                "model_load_ms": 320.0,
                "inference_ms": 650.0,
                "peak_vram_mb": 42.0,
                "input_bars": 20,
                "forecast_bars": 5,
            },
        }
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            with patch.dict(
                "os.environ",
                {
                    "KRONOS_ENABLED": "true",
                    "KRONOS_RECORD_PATH": str(Path(temp_dir) / "kronos.jsonl"),
                },
            ):
                service = KronosForecastService(
                    stock_service=FakeKronosStockService(),
                    dependency_probe=lambda: {
                        "pandas": True,
                        "torch": True,
                        "einops": True,
                        "safetensors": True,
                        "huggingface_hub": True,
                        "model": True,
                    },
                )
                with patch.object(service, "_run_kronos_model", return_value=model_result):
                    result = service.forecast("AAPL", lookback=20, horizon=5, allow_model=True)

        self.assertEqual(result["status"], "model_ready")
        self.assertTrue(result["kronos_model_used"])
        self.assertEqual(result["runtime_metrics"]["resolved_device"], "cuda")
        self.assertEqual(result["runtime_metrics"]["forecast_bars"], 5)

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
                        "einops": True,
                        "safetensors": True,
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
                        "einops": True,
                        "safetensors": True,
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

    def test_availability_uses_official_kronos_runtime_dependencies(self) -> None:
        from src.services.kronos_forecast_service import KronosForecastService

        with patch.dict("os.environ", {"KRONOS_ENABLED": "true"}, clear=False):
            service = KronosForecastService(
                stock_service=FakeKronosStockService(),
                dependency_probe=lambda: {
                    "pandas": True,
                    "torch": True,
                    "einops": True,
                    "safetensors": True,
                    "huggingface_hub": True,
                    "model": True,
                },
            )
            availability = service.check_availability()

        self.assertEqual(availability["status"], "model_ready")
        self.assertEqual(availability["missing_dependencies"], [])
        self.assertEqual(availability["model_id"], "NeoQuasar/Kronos-mini")
        self.assertEqual(availability["tokenizer_id"], "NeoQuasar/Kronos-Tokenizer-2k")

    def test_forecast_times_out_slow_history_and_returns_local_fallback(self) -> None:
        from src.services.kronos_forecast_service import KronosForecastService

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            record_path = Path(temp_dir) / "kronos.jsonl"
            with patch.dict("os.environ", {"KRONOS_ENABLED": "false", "KRONOS_RECORD_PATH": str(record_path)}):
                service = KronosForecastService(
                    stock_service=SlowHistoryKronosStockService(),
                    dependency_probe=lambda: {
                        "pandas": True,
                        "torch": True,
                        "einops": True,
                        "safetensors": True,
                        "huggingface_hub": True,
                        "model": False,
                    },
                    data_timeout_seconds=0.05,
                )

                started = time.perf_counter()
                result = service.forecast("600519", lookback=20, horizon=5)
                elapsed = time.perf_counter() - started

            self.assertLess(elapsed, 0.5)
            self.assertEqual(result["status"], "model_disabled")
            self.assertFalse(result["kronos_model_used"])
            self.assertGreaterEqual(len(result["forecast_points"]), 5)
            self.assertIn("Kronos market data fetch timed out; local rules fallback used.", result["warnings"])
            self.assertIn("K-line context is short; confidence is capped.", result["warnings"])


if __name__ == "__main__":
    unittest.main()

"""Regression tests for bounded A-share history routing."""

import os
import time
import unittest
from unittest.mock import Mock, patch

import pandas as pd

from data_provider.base import DataFetchError, DataFetcherManager
from data_provider.pytdx_fetcher import PytdxFetcher
from src.services.stock_service import StockService


class PlatformHistoryResilienceV94TestCase(unittest.TestCase):
    def test_unconfigured_pytdx_is_not_auto_discovered(self) -> None:
        with patch.dict(
            os.environ,
            {
                "PYTDX_SERVERS": "",
                "PYTDX_HOST": "",
                "PYTDX_PORT": "",
                "PYTDX_AUTO_DISCOVERY_ENABLED": "false",
            },
            clear=False,
        ):
            fetcher = PytdxFetcher()

        self.assertFalse(fetcher.is_available_for_request("daily_data"))

    def test_explicit_pytdx_server_remains_available(self) -> None:
        fetcher = PytdxFetcher(hosts=[("127.0.0.1", 7709)])
        self.assertTrue(fetcher.is_available_for_request("daily_data"))

    def test_daily_route_stops_when_total_deadline_expires(self) -> None:
        class SlowFetcher:
            name = "SlowFetcher"
            priority = 0

            def is_available_for_request(self, _capability: str = "") -> bool:
                return True

            def get_daily_data(self, **_kwargs):
                time.sleep(0.25)
                return pd.DataFrame()

        manager = DataFetcherManager(fetchers=[SlowFetcher()])
        started = time.monotonic()

        with self.assertRaises(DataFetchError):
            manager.get_daily_data("600519", days=5, timeout_seconds=0.05)

        self.assertLess(time.monotonic() - started, 0.18)

    def test_stock_service_exposes_history_source_and_passes_timeout(self) -> None:
        manager = Mock()
        manager.get_daily_data.return_value = (
            pd.DataFrame(
                [
                    {
                        "date": "2026-07-09",
                        "open": 100.0,
                        "high": 102.0,
                        "low": 99.0,
                        "close": 101.0,
                        "volume": 1000.0,
                        "amount": 101000.0,
                        "pct_chg": 1.0,
                    }
                ]
            ),
            "EfinanceFetcher",
        )
        manager.get_stock_name.return_value = "Test Stock"

        with patch("data_provider.base.DataFetcherManager", return_value=manager):
            result = StockService().get_history_data("600519", days=5)

        self.assertEqual(result["source"], "EfinanceFetcher")
        manager.get_daily_data.assert_called_once()
        self.assertIn("timeout_seconds", manager.get_daily_data.call_args.kwargs)
        self.assertGreater(manager.get_daily_data.call_args.kwargs["timeout_seconds"], 0)


if __name__ == "__main__":
    unittest.main()

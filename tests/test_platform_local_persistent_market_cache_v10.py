# -*- coding: utf-8 -*-
import importlib.util
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.basic_query_service import BasicQueryService
from src.services.market_source_health import MarketSourceHealthRegistry
from src.services.persistent_market_data_cache import PersistentMarketDataCache


def _history_rows(count: int = 24) -> list[dict]:
    return [
        {
            "date": f"2026-06-{day:02d}",
            "open": 90.0 + day,
            "high": 92.0 + day,
            "low": 89.0 + day,
            "close": 91.0 + day,
            "volume": 1000 + day * 10,
        }
        for day in range(1, count + 1)
    ]


def _quote(code: str = "HK00700", *, source: str = "unit_quote") -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "current_price": 388.8,
        "change_percent": 1.2,
        "volume": 1000,
        "amount": 388800.0,
        "source": source,
        "update_time": "2026-07-02T09:30:00",
    }


def _history(code: str = "HK00700", *, source: str = "unit_history") -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "source": source,
        "period": "daily",
        "data": _history_rows(),
    }


class PlatformLocalPersistentMarketCacheV10TestCase(unittest.TestCase):
    def test_persistent_cache_survives_new_instance_and_marks_disk_origin(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            cache_path = Path(temp_dir) / "market-cache.json"
            first = PersistentMarketDataCache(path=cache_path, default_ttl_seconds=60)
            first.set("quote:HK00700", _quote(source="hk_realtime"), source="hk_realtime")

            second = PersistentMarketDataCache(path=cache_path, default_ttl_seconds=60)
            hit = second.get("quote:HK00700")

        self.assertIsNotNone(hit)
        self.assertEqual(hit.value["current_price"], 388.8)
        self.assertEqual(hit.source, "hk_realtime")
        self.assertEqual(hit.freshness, "cached")
        self.assertEqual(hit.origin, "disk")

    def test_basic_query_uses_stale_disk_cache_during_source_cooldown_without_live_call(self) -> None:
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            cache_path = Path(temp_dir) / "market-cache.json"
            first = PersistentMarketDataCache(path=cache_path, default_ttl_seconds=0)
            first.set("quote:HK00700", _quote(source="hk_realtime"), source="hk_realtime")
            first.set("history:HK00700:daily:30", _history(source="hk_history"), source="hk_history")
            time.sleep(0.01)

            stock_service = MagicMock()
            stock_service.get_realtime_quote.side_effect = AssertionError("disk cache should avoid live quote")
            stock_service.get_history_data.side_effect = AssertionError("disk cache should avoid live history")
            health = MarketSourceHealthRegistry(failure_threshold=2, cooling_seconds=60)
            health.record_timeout("hk_realtime", elapsed_ms=4000)
            health.record_timeout("hk_realtime", elapsed_ms=4000)
            health.record_timeout("hk_history", elapsed_ms=4000)
            health.record_timeout("hk_history", elapsed_ms=4000)
            cache = PersistentMarketDataCache(path=cache_path, default_ttl_seconds=0)
            service = BasicQueryService(
                stock_service=stock_service,
                cache=cache,
                source_health=health,
                fetch_timeout_seconds=0.01,
            )

            with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
                snapshot = service.get_snapshot("HK00700")

        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(snapshot["quote"]["freshness"], "stale")
        self.assertEqual(snapshot["diagnostics"]["cache"]["quote"], "stale_fallback")
        self.assertEqual(snapshot["diagnostics"]["cache"]["history"], "stale_fallback")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "stale_disk_cache")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["history"], "stale_disk_cache")
        self.assertEqual(snapshot["diagnostics"]["persistent_cache"]["quote"], "disk")
        self.assertEqual(snapshot["diagnostics"]["persistent_cache"]["history"], "disk")
        self.assertEqual(snapshot["diagnostics"]["persistent_cache"]["mode"], "local_json")
        self.assertEqual(snapshot["diagnostics"]["source_health"]["quote"]["status"], "cooling_down")
        self.assertTrue(any(warning["code"] == "stale_quote" for warning in snapshot["warnings"]))
        stock_service.get_realtime_quote.assert_not_called()
        stock_service.get_history_data.assert_not_called()

    def test_v10_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_persistent_market_cache_v10.py"

        self.assertTrue(verifier.exists(), "V10 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_persistent_market_cache_v10"))

        from scripts.verify_platform_local_persistent_market_cache_v10 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_PERSISTENT_MARKET_CACHE_V10_OK")

    def test_v10_evaluator_requires_persistent_cache_diagnostics(self) -> None:
        from scripts.verify_platform_local_persistent_market_cache_v10 import evaluate_snapshot_persistent_cache

        missing = evaluate_snapshot_persistent_cache(
            {
                "HK00700": {
                    "status_code": 200,
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "fallback": {"quote": "live", "history": "live"},
                    },
                }
            }
        )
        valid = evaluate_snapshot_persistent_cache(
            {
                "HK00700": {
                    "status_code": 200,
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "fallback": {"quote": "stale_disk_cache", "history": "stale_disk_cache"},
                        "persistent_cache": {"quote": "disk", "history": "disk", "mode": "local_json"},
                    },
                }
            }
        )

        self.assertIn("HK00700", missing)
        self.assertEqual(valid, [])


if __name__ == "__main__":
    unittest.main()

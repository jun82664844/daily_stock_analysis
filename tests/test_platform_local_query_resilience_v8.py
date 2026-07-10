# -*- coding: utf-8 -*-
import importlib.util
import subprocess
import sys
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from src.services.basic_query_service import BasicQueryService
from src.services.market_data_cache import MarketDataCache


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


def _quote(code: str = "AAPL", *, source: str = "unit_quote") -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "current_price": 200.0,
        "change_percent": 1.5,
        "volume": 1000,
        "amount": 200000.0,
        "source": source,
        "update_time": "2026-07-02T09:30:00",
    }


def _history(code: str = "AAPL", *, source: str = "unit_history") -> dict:
    return {
        "stock_code": code,
        "stock_name": code,
        "source": source,
        "period": "daily",
        "data": _history_rows(),
    }


class PlatformLocalQueryResilienceV8TestCase(unittest.TestCase):
    def test_quote_timeout_returns_fast_degraded_no_ai_snapshot(self) -> None:
        stock_service = MagicMock()

        def slow_quote(_code: str):
            time.sleep(0.2)
            return _quote(_code, source="slow_quote")

        stock_service.get_realtime_quote.side_effect = slow_quote
        stock_service.get_history_data.return_value = _history("600519", source="unit_history")
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
            fetch_timeout_seconds=0.01,
        )

        started = time.perf_counter()
        with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
            snapshot = service.get_snapshot("600519")
        elapsed = time.perf_counter() - started

        self.assertLess(elapsed, 0.18)
        self.assertFalse(snapshot["ai_used"])
        self.assertEqual(snapshot["market"], "cn")
        self.assertEqual(snapshot["quote"]["freshness"], "unavailable")
        self.assertEqual(snapshot["degradation"]["status"], "degraded")
        self.assertTrue(any(warning["code"] == "quote_timeout" for warning in snapshot["warnings"]))
        self.assertTrue(any(warning["code"] == "missing_quote" for warning in snapshot["warnings"]))
        self.assertIsNotNone(snapshot["indicators"]["ma20"])

        diagnostics = snapshot["diagnostics"]
        self.assertEqual(diagnostics["timeouts"]["quote"], True)
        self.assertEqual(diagnostics["timeouts"]["history"], False)
        self.assertEqual(diagnostics["errors"]["quote"], "timeout")
        self.assertEqual(diagnostics["fallback"]["quote"], "none")
        self.assertEqual(diagnostics["fallback"]["history"], "live")
        self.assertEqual(diagnostics["performance"]["status"], "slow")

    def test_stale_cache_revalidates_once_and_marks_fallback_when_sources_error(self) -> None:
        cache = MarketDataCache(default_ttl_seconds=0)
        cache.set("quote:HK00700", _quote("HK00700", source="stale_quote"), source="stale_quote")
        cache.set("history:HK00700:daily:30", _history("HK00700", source="stale_history"), source="stale_history")
        time.sleep(0.01)
        stock_service = MagicMock()
        stock_service.get_realtime_quote.side_effect = RuntimeError("live quote failed")
        stock_service.get_history_data.side_effect = RuntimeError("live history failed")
        service = BasicQueryService(
            stock_service=stock_service,
            cache=cache,
            fetch_timeout_seconds=0.01,
        )

        with patch.object(service, "_comparison_targets_with_reference_quotes", return_value=[]):
            snapshot = service.get_snapshot("HK00700")

        self.assertEqual(snapshot["market"], "hk")
        self.assertEqual(snapshot["quote"]["freshness"], "stale")
        self.assertEqual(snapshot["diagnostics"]["cache"]["quote"], "stale_fallback")
        self.assertEqual(snapshot["diagnostics"]["cache"]["history"], "stale_fallback")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "stale_cache")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["history"], "stale_cache")
        self.assertEqual(snapshot["diagnostics"]["timeouts"]["quote"], False)
        self.assertTrue(any(warning["code"] == "stale_quote" for warning in snapshot["warnings"]))
        stock_service.get_realtime_quote.assert_called_once_with("HK00700")
        stock_service.get_history_data.assert_called_once_with("HK00700", period="daily", days=30)

    def test_history_timeout_returns_quote_with_missing_history_warning(self) -> None:
        stock_service = MagicMock()
        stock_service.get_realtime_quote.return_value = _quote("AAPL", source="unit_quote")

        def slow_history(_code: str, **_kwargs):
            time.sleep(0.2)
            return _history(_code, source="slow_history")

        stock_service.get_history_data.side_effect = slow_history
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
            fetch_timeout_seconds=0.01,
        )

        snapshot = service.get_snapshot("AAPL")

        self.assertEqual(snapshot["quote"]["freshness"], "fresh")
        self.assertEqual(snapshot["diagnostics"]["timeouts"]["history"], True)
        self.assertEqual(snapshot["diagnostics"]["errors"]["history"], "timeout")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["quote"], "live")
        self.assertEqual(snapshot["diagnostics"]["fallback"]["history"], "none")
        self.assertTrue(any(warning["code"] == "history_timeout" for warning in snapshot["warnings"]))
        self.assertTrue(any(warning["code"] == "missing_history" for warning in snapshot["warnings"]))

    def test_v8_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_query_resilience_v8.py"

        self.assertTrue(verifier.exists(), "V8 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_query_resilience_v8"))

        from scripts.verify_platform_local_query_resilience_v8 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK")

    def test_v8_resilience_evaluator_requires_timeout_and_fallback_diagnostics(self) -> None:
        from scripts.verify_platform_local_query_resilience_v8 import evaluate_snapshot_resilience

        missing = evaluate_snapshot_resilience(
            {
                "AAPL": {
                    "status_code": 200,
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "cache": {"quote": "miss", "history": "miss"},
                    },
                }
            }
        )
        valid = evaluate_snapshot_resilience(
            {
                "AAPL": {
                    "status_code": 200,
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "cache": {"quote": "miss", "history": "miss"},
                        "timeouts": {"quote": False, "history": False},
                        "errors": {"quote": None, "history": None},
                        "fallback": {"quote": "live", "history": "live"},
                    },
                }
            }
        )

        self.assertIn("AAPL", missing)
        self.assertEqual(valid, [])

    def test_script_path_execution_imports_local_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            project_root = Path(temp_dir)
            for rel_path in (
                "scripts/verify_platform_local_query_resilience_v8.py",
                "tests/test_platform_local_query_resilience_v8.py",
                "docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md",
            ):
                path = project_root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# local query resilience v8\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "verify_platform_local_query_resilience_v8.py"),
                    "--project-root",
                    str(project_root),
                    "--skip-live",
                    "--skip-subprocess",
                    "--json",
                ],
                cwd=root,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )

        self.assertEqual(completed.returncode, 0, completed.stderr + completed.stdout)
        self.assertIn("DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()

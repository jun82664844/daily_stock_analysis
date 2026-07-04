# -*- coding: utf-8 -*-
import importlib.util
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from api.v1.schemas.basic_query import BasicStockSnapshot
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
        "stock_name": "Apple Inc.",
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
        "stock_name": "Apple Inc.",
        "source": source,
        "period": "daily",
        "data": _history_rows(),
    }


class PlatformLocalQuerySpeedV7TestCase(unittest.TestCase):
    def test_quick_snapshot_returns_timing_cache_source_and_freshness_diagnostics(self) -> None:
        stock_service = MagicMock()
        stock_service.get_realtime_quote.return_value = _quote()
        stock_service.get_history_data.return_value = _history()
        service = BasicQueryService(
            stock_service=stock_service,
            cache=MarketDataCache(default_ttl_seconds=60),
        )

        first = service.get_snapshot("AAPL")
        second = service.get_snapshot("AAPL")

        first_diag = first["diagnostics"]
        self.assertFalse(first["ai_used"])
        self.assertGreaterEqual(first_diag["elapsed_ms"], 0)
        self.assertGreaterEqual(first_diag["quote_elapsed_ms"], 0)
        self.assertGreaterEqual(first_diag["history_elapsed_ms"], 0)
        self.assertEqual(first_diag["cache"]["quote"], "miss")
        self.assertEqual(first_diag["cache"]["history"], "miss")
        self.assertEqual(first_diag["sources"]["quote"], "unit_quote")
        self.assertEqual(first_diag["sources"]["history"], "unit_history")
        self.assertEqual(first_diag["freshness"]["quote"], "fresh")
        self.assertEqual(first_diag["freshness"]["history"], "fresh")
        self.assertIn(first_diag["performance"]["status"], {"ok", "slow"})
        self.assertEqual(first_diag["route_lane"], "us_market_data")

        second_diag = second["diagnostics"]
        self.assertEqual(second_diag["cache"]["quote"], "hit")
        self.assertEqual(second_diag["cache"]["history"], "hit")
        self.assertEqual(second_diag["freshness"]["quote"], "cached")
        self.assertEqual(second_diag["freshness"]["history"], "cached")
        stock_service.get_realtime_quote.assert_called_once_with("AAPL")
        stock_service.get_history_data.assert_called_once_with("AAPL", period="daily", days=30)

    def test_basic_snapshot_schema_preserves_query_diagnostics(self) -> None:
        snapshot = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "quote": {"current_price": 200.0, "source": "unit_quote", "freshness": "fresh"},
            "indicators": {"ma5": 199.0, "volume_price_signal": "neutral"},
            "route": {
                "input_code": "AAPL",
                "normalized_code": "AAPL",
                "market": "us",
                "channel": "us_equity",
                "data_source_lane": "us_market_data",
                "quote_sources": ["unit_quote"],
                "history_sources": ["unit_history"],
                "ai_required": False,
            },
            "warnings": [],
            "degradation": {"status": "ok", "severity": "info", "message": "Market data ready"},
            "diagnostics": {
                "elapsed_ms": 5,
                "quote_elapsed_ms": 2,
                "history_elapsed_ms": 3,
                "cache": {"quote": "miss", "history": "miss"},
                "sources": {"quote": "unit_quote", "history": "unit_history"},
                "freshness": {"quote": "fresh", "history": "fresh"},
                "route_lane": "us_market_data",
                "performance": {"status": "ok", "slow_threshold_ms": 3000},
            },
            "ai_used": False,
        }

        payload = BasicStockSnapshot.model_validate(snapshot).model_dump()

        self.assertIn("diagnostics", payload)
        self.assertEqual(payload["diagnostics"]["cache"]["quote"], "miss")
        self.assertEqual(payload["diagnostics"]["sources"]["history"], "unit_history")
        self.assertFalse(payload["ai_used"])

    def test_v7_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_query_speed_v7.py"

        self.assertTrue(verifier.exists(), "V7 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_query_speed_v7"))

        from scripts.verify_platform_local_query_speed_v7 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK")

    def test_v7_verifier_evaluator_requires_diagnostics_for_successful_snapshots(self) -> None:
        from scripts.verify_platform_local_query_speed_v7 import evaluate_market_snapshot_diagnostics

        missing = evaluate_market_snapshot_diagnostics(
            {
                "AAPL": {
                    "status_code": 200,
                    "market": "us",
                    "ai_used": False,
                    "lane": "us_market_data",
                    "diagnostics": {},
                }
            }
        )
        valid = evaluate_market_snapshot_diagnostics(
            {
                "AAPL": {
                    "status_code": 200,
                    "market": "us",
                    "ai_used": False,
                    "lane": "us_market_data",
                    "diagnostics": {
                        "elapsed_ms": 10,
                        "quote_elapsed_ms": 4,
                        "history_elapsed_ms": 6,
                        "cache": {"quote": "miss", "history": "miss"},
                        "sources": {"quote": "unit_quote", "history": "unit_history"},
                        "freshness": {"quote": "fresh", "history": "fresh"},
                        "performance": {"status": "ok", "slow_threshold_ms": 3000},
                    },
                }
            }
        )

        self.assertIn("AAPL", missing)
        self.assertEqual(valid, [])

    def test_v7_verifier_is_not_hidden_by_gitignore(self) -> None:
        root = Path(__file__).resolve().parents[1]
        rel_path = "scripts/verify_platform_local_query_speed_v7.py"
        completed = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )

        self.assertNotEqual(completed.returncode, 0, f"{rel_path} is hidden by .gitignore")

    def test_script_path_execution_imports_local_dependencies(self) -> None:
        root = Path(__file__).resolve().parents[1]
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            project_root = Path(temp_dir)
            (project_root / "scripts").mkdir(parents=True, exist_ok=True)
            (project_root / "docs" / "superpowers" / "plans").mkdir(parents=True, exist_ok=True)
            for rel_path in (
                "scripts/verify_platform_local_query_speed_v7.py",
                "tests/test_platform_local_query_speed_v7.py",
                "docs/superpowers/plans/2026-07-02-dsa-local-v7-query-speed.md",
            ):
                path = project_root / rel_path
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("# local query speed v7\n", encoding="utf-8")

            completed = subprocess.run(
                [
                    sys.executable,
                    str(root / "scripts" / "verify_platform_local_query_speed_v7.py"),
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
        self.assertIn("DSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK", completed.stdout)


if __name__ == "__main__":
    unittest.main()

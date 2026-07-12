from __future__ import annotations

import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app


class KronosForecastApiV58TestCase(unittest.TestCase):
    def test_public_kronos_forecast_reports_model_unavailable_without_ai(self) -> None:
        client = TestClient(create_app())
        fake_payload = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "mode": "kronos_sandbox",
            "status": "model_unavailable",
            "provider": "kronos",
            "source": "local_kline_rules_kronos_unavailable",
            "horizon": "next_5_bars",
            "lookback": 20,
            "direction": "upside_bias",
            "confidence": 64,
            "support": 190.0,
            "resistance": 205.0,
            "adapter_status": "Kronos dependencies missing: torch, model.",
            "enabled": True,
            "kronos_model_used": False,
            "model_id": "NeoQuasar/Kronos-small",
            "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-base",
            "device": "auto",
            "dependency_status": {"torch": False, "model": False},
            "missing_dependencies": ["torch", "model"],
            "scenarios": [
                {
                    "label": "Upside-biased preview",
                    "direction": "upside_bias",
                    "probability": 64,
                    "trigger": "Hold above support.",
                    "detail": "Local rules fallback.",
                }
            ],
            "forecast_points": [],
            "backtest_summary": {"records": 0, "evaluated": 0, "hits": 0, "hit_rate": None},
            "warnings": ["Kronos model unavailable; local rules fallback only."],
            "elapsed_ms": 1.0,
            "cache_hit": False,
            "record_id": "unit-record",
            "ai_used": False,
            "public_search_used": False,
            "boundary": "Experimental model preview; information analysis only; not investment advice.",
        }

        with patch("api.v1.endpoints.stocks.KronosForecastService") as service_cls:
            service_cls.return_value.forecast.return_value = fake_payload
            response = client.get("/api/v1/stocks/AAPL/kronos-forecast?lookback=20&horizon=5")

        self.assertEqual(response.status_code, 200)
        data = response.json()
        self.assertEqual(data["status"], "model_unavailable")
        self.assertFalse(data["ai_used"])
        self.assertFalse(data["public_search_used"])
        self.assertFalse(data["kronos_model_used"])
        self.assertIn("torch", data["missing_dependencies"])

    def test_require_model_rejects_anonymous_before_model_run(self) -> None:
        client = TestClient(create_app())

        response = client.get("/api/v1/stocks/AAPL/kronos-forecast?require_model=true")

        self.assertEqual(response.status_code, 401)
        self.assertEqual(response.json()["error"], "login_required")

    def test_explicit_pro_request_grants_model_permission_to_service(self) -> None:
        client = TestClient(create_app())
        payload = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "mode": "kronos_sandbox",
            "status": "model_ready",
            "provider": "kronos",
            "source": "kronos_model_local",
            "horizon": "next_5_bars",
            "lookback": 20,
            "direction": "range_watch",
            "confidence": 60,
            "support": 190.0,
            "resistance": 205.0,
            "adapter_status": "Kronos model ran locally.",
            "enabled": True,
            "kronos_model_used": True,
            "model_id": "NeoQuasar/Kronos-mini",
            "tokenizer_id": "NeoQuasar/Kronos-Tokenizer-2k",
            "device": "cuda",
            "dependency_status": {"torch": True, "model": True},
            "missing_dependencies": [],
            "runtime_metrics": {
                "resolved_device": "cuda",
                "model_cache_hit": False,
                "model_load_ms": 320.0,
                "inference_ms": 650.0,
                "peak_vram_mb": 42.0,
                "input_bars": 20,
                "forecast_bars": 5,
            },
            "scenarios": [],
            "forecast_points": [],
            "backtest_summary": {"records": 0, "evaluated": 0, "hits": 0, "hit_rate": None},
            "warnings": [],
            "elapsed_ms": 970.0,
            "cache_hit": False,
            "record_id": "unit-real-kronos",
            "ai_used": False,
            "public_search_used": False,
            "boundary": "Experimental model preview; information analysis only; not investment advice.",
        }
        identity = SimpleNamespace(is_admin=False, plan="pro")

        with (
            patch("api.v1.endpoints.stocks.platform_identity_from_request", return_value=identity),
            patch("api.v1.endpoints.stocks.KronosForecastService") as service_cls,
        ):
            service_cls.return_value.forecast.return_value = payload
            response = client.get("/api/v1/stocks/AAPL/kronos-forecast?lookback=20&horizon=5&require_model=true")

        self.assertEqual(response.status_code, 200)
        service_cls.return_value.forecast.assert_called_once_with(
            "AAPL",
            lookback=20,
            horizon=5,
            allow_model=True,
        )


if __name__ == "__main__":
    unittest.main()

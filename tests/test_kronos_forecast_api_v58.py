from __future__ import annotations

import unittest
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


if __name__ == "__main__":
    unittest.main()

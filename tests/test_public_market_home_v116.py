# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import time
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from pydantic import ValidationError

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _security(symbol: str, turnover: float | None, change: float | None) -> dict:
    return {
        "symbol": symbol, "name": symbol, "market": "us", "currency": "USD",
        "current_price": 100, "change_percent": change, "turnover": turnover,
        "source_state": {"source": "unit_quote", "status": "fresh", "observed_at": "2026-07-13T01:30:00Z"},
    }


def _overview(market: str) -> dict:
    items = [_security(f"{market}-LOW", 10, -5), _security(f"{market}-HIGH", 30, 1), _security(f"{market}-NONE", None, 9)]
    for item in items:
        item["market"] = market
    return {
        "market": market, "session_state": "unknown", "indices": items[:1], "movers": items,
        "headlines": [{
            "title": f"{market.upper()} market bulletin",
            "summary": "Objective market information.",
            "publisher": "Unit News",
            "published_at": "2026-07-13T01:25:00Z",
            "url": "https://example.com/market-bulletin",
            "source_state": {
                "source": "unit_news",
                "status": "fresh",
                "observed_at": "2026-07-13T01:25:00Z",
            },
        }],
        "sources": [{"source": f"{market}_snapshot", "status": "fresh"}], "warnings": [],
    }


class _Workspace:
    def __init__(self, *, failed: str | None = None, delay: float = 0) -> None:
        self.failed = failed
        self.delay = delay
        self.calls: list[str] = []

    def get_overview(self, market: str) -> dict:
        self.calls.append(market)
        if self.delay:
            time.sleep(self.delay)
        if market == self.failed:
            raise RuntimeError("provider unavailable")
        return _overview(market)


class _HomeContextWorkspace(_Workspace):
    def get_overview(self, market: str) -> dict:
        body = super().get_overview(market)
        body["warnings"] = [*body.get("warnings", []), "market_quotes_unavailable"]
        body["sources"] = [
            *body.get("sources", []),
            {"source": f"{market}_market_snapshot", "status": "unavailable"},
        ]
        return body


class _Rankings:
    def __init__(self, *, failed: str | None = None) -> None:
        self.failed = failed

    def load(self, market: str) -> dict:
        if market == self.failed:
            raise RuntimeError("ranking provider unavailable")
        active = _security(f"{market}-ACTIVE", 100, 2)
        gainer = _security(f"{market}-GAIN", 80, 8)
        loser = _security(f"{market}-LOSS", 70, -7)
        for item in (active, gainer, loser):
            item["market"] = market
        return {
            "market": market,
            "as_of": "2026-07-14T02:02:00Z",
            "most_active": [active],
            "gainers": [gainer],
            "losers": [loser],
            "sector_highlights": [],
            "sources": [{"source": f"{market}_public_ranking", "status": "fresh"}],
            "warnings": [],
            "cache": {"hit": False, "age_seconds": 0, "ttl_seconds": 120},
            "ai_used": False,
            "informational_only": True,
        }


class _FlakyRankings(_Rankings):
    def __init__(self) -> None:
        super().__init__()
        self.calls: dict[str, int] = {}

    def load(self, market: str) -> dict:
        self.calls[market] = self.calls.get(market, 0) + 1
        if market == "hk" and self.calls[market] == 1:
            raise RuntimeError("temporary ranking provider failure")
        return super().load(market)


class PublicMarketHomeServiceV116TestCase(unittest.TestCase):
    def test_v127_event_contract_keeps_safe_defaults_for_v126_payloads(self) -> None:
        from api.v1.schemas.market_workspace import PublicMarketEvent

        event = PublicMarketEvent.model_validate({
            "event_id": "legacy-event",
            "market": "cn",
            "category": "market",
            "title": "市场成交保持活跃",
            "event_time": "2026-07-14T03:00:00Z",
            "time_kind": "published",
            "source_state": {"source": "unit_news", "status": "fresh"},
            "classification_source": "keyword_rules",
        })

        self.assertEqual(event.relevance_score, 0)
        self.assertEqual(event.importance, "low")
        self.assertEqual(event.relevance_reasons, [])
        self.assertEqual(event.source_count, 1)
        self.assertEqual(event.source_publishers, [])
        self.assertEqual(event.source_records, [])

    def test_v129_event_contract_limits_source_records(self) -> None:
        from api.v1.schemas.market_workspace import PublicMarketEvent

        payload = {
            "event_id": "bounded-event",
            "market": "us",
            "category": "market",
            "title": "US market update",
            "event_time": "2026-07-14T03:00:00Z",
            "time_kind": "published",
            "source_state": {"source": "unit_news", "status": "fresh"},
            "classification_source": "keyword_rules",
            "source_records": [
                {
                    "publisher": f"Publisher {index}",
                    "source": f"source_{index}",
                    "url": f"https://example.com/{index}",
                    "event_time": "2026-07-14T03:00:00Z",
                    "time_kind": "published",
                }
                for index in range(9)
            ],
        }

        with self.assertRaises(ValidationError):
            PublicMarketEvent.model_validate(payload)

    def test_workspace_attention_symbols_are_configurable_and_deduplicated(self) -> None:
        from src.services.market_workspace_service import MarketWorkspaceService

        with patch.dict(os.environ, {
            "PLATFORM_PUBLIC_MARKET_HOME_SYMBOLS_US": "AAPL,MSFT,AAPL",
        }, clear=False):
            service = MarketWorkspaceService(snapshot_loader=lambda symbol: {"stock_code": symbol})
        self.assertEqual(service.market_symbols["us"], ("AAPL", "MSFT"))

    def test_builds_fixed_three_market_order_without_ai(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        service = PublicMarketHomeService(_Workspace(), timeout_seconds=1)
        body = service.build()

        self.assertEqual([item["market"] for item in body["markets"]], ["cn", "hk", "us"])
        self.assertFalse(body["ai_used"])
        self.assertTrue(body["informational_only"])
        self.assertEqual(body["markets"][0]["ranking_scope"], "configured_universe")
        self.assertEqual(body["markets"][0]["display_mode"], "latest_available")
        self.assertEqual([item["symbol"] for item in body["markets"][0]["attention"]], ["cn-HIGH", "cn-LOW", "cn-NONE"])
        self.assertEqual(body["markets"][0]["headlines"][0]["title"], "CN market bulletin")

    def test_one_market_failure_does_not_blank_other_markets(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        body = PublicMarketHomeService(_Workspace(failed="hk"), timeout_seconds=1).build()
        self.assertTrue(body["markets"][0]["attention"])
        self.assertEqual(body["markets"][1]["warnings"], ["market_home_unavailable"])
        self.assertEqual(body["markets"][1]["headlines"], [])
        self.assertTrue(body["markets"][2]["attention"])

    def test_three_markets_load_concurrently_under_one_deadline(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        started = time.perf_counter()
        body = PublicMarketHomeService(_Workspace(delay=0.1), timeout_seconds=0.3).build()
        elapsed = time.perf_counter() - started
        self.assertLess(elapsed, 0.24)
        self.assertTrue(all(item["attention"] for item in body["markets"]))

    def test_dynamic_rankings_replace_configured_attention_and_keep_market_groups(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        body = PublicMarketHomeService(
            _HomeContextWorkspace(),
            ranking_loader=_Rankings().load,
            timeout_seconds=1,
        ).build()
        cn = body["markets"][0]

        self.assertEqual(cn["ranking_scope"], "market_wide")
        self.assertEqual([item["symbol"] for item in cn["most_active"]], ["cn-ACTIVE"])
        self.assertEqual([item["symbol"] for item in cn["gainers"]], ["cn-GAIN"])
        self.assertEqual([item["symbol"] for item in cn["losers"]], ["cn-LOSS"])
        self.assertEqual(cn["attention"], cn["most_active"])
        self.assertNotIn("cn-HIGH", {item["symbol"] for item in cn["attention"]})
        self.assertNotIn("market_quotes_unavailable", cn["warnings"])
        self.assertFalse(any(str(item.get("source", "")).endswith("_market_snapshot") for item in cn["sources"]))

    def test_dynamic_ranking_failure_never_falls_back_to_fixed_pool(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        body = PublicMarketHomeService(
            _Workspace(),
            ranking_loader=_Rankings(failed="hk").load,
            timeout_seconds=1,
        ).build()
        hk = body["markets"][1]

        self.assertEqual(hk["attention"], [])
        self.assertEqual(hk["most_active"], [])
        self.assertIn("market_rankings_unavailable", hk["warnings"])
        self.assertTrue(hk["headlines"])

    def test_partial_dynamic_failure_is_not_cached_as_a_complete_home(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        rankings = _FlakyRankings()
        service = PublicMarketHomeService(
            _Workspace(),
            ranking_loader=rankings.load,
            timeout_seconds=1,
            cache_ttl_seconds=60,
        )
        first = service.build()
        second = service.build()

        self.assertEqual(first["markets"][1]["ranking_scope"], "unavailable")
        self.assertEqual(second["markets"][1]["ranking_scope"], "market_wide")
        self.assertEqual(rankings.calls["hk"], 2)

    def test_v119_default_deadline_allows_dynamic_ranking_deadline(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        with patch.dict(os.environ, {}, clear=True):
            service = PublicMarketHomeService(_Workspace(), ranking_loader=_Rankings().load)
        self.assertGreaterEqual(service.timeout_seconds, 5.5)

    def test_v126_adds_structured_events_without_changing_ai_boundary(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        captured: dict = {}

        def build_events(markets: list[dict], as_of: str) -> list[dict]:
            captured["markets"] = markets
            captured["as_of"] = as_of
            return [{
                "event_id": "event-1",
                "market": "us",
                "category": "earnings",
                "title": "AAPL earnings results published",
                "summary": "Objective public information.",
                "symbol": None,
                "name": None,
                "event_time": as_of,
                "time_kind": "retrieved",
                "publisher": "Unit News",
                "url": "https://example.com/event",
                "source_state": {"source": "unit_news", "status": "fresh"},
                "classification_source": "keyword_rules",
            }]

        body = PublicMarketHomeService(
            _Workspace(),
            timeout_seconds=1,
            event_builder=build_events,
        ).build()

        self.assertEqual(body["events"][0]["category"], "earnings")
        self.assertEqual([item["market"] for item in captured["markets"]], ["cn", "hk", "us"])
        self.assertEqual(captured["as_of"], body["as_of"])
        self.assertFalse(body["ai_used"])
        self.assertTrue(body["informational_only"])

    def test_v126_event_failure_is_fail_open_and_truthfully_warned(self) -> None:
        from src.services.public_market_home_service import PublicMarketHomeService

        def fail_events(_markets: list[dict], _as_of: str) -> list[dict]:
            raise RuntimeError("event normalization unavailable")

        body = PublicMarketHomeService(
            _Workspace(),
            timeout_seconds=1,
            event_builder=fail_events,
        ).build()

        self.assertEqual(body["events"], [])
        self.assertTrue(all(item["attention"] for item in body["markets"]))
        self.assertTrue(all("market_events_unavailable" in item["warnings"] for item in body["markets"]))


class PublicMarketHomeEndpointV116TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_home_is_public_when_both_feature_flags_are_enabled(self) -> None:
        env = {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "public-home.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "true",
            "PLATFORM_USER_AUTH_ENABLED": "true",
            "ADMIN_AUTH_ENABLED": "true",
        }
        with patch.dict(os.environ, env, clear=False), patch(
            "api.v1.endpoints.market_workspace._public_home_service.build",
            return_value={"as_of": "2026-07-13T01:30:00Z", "markets": [], "ai_used": False, "informational_only": True},
        ):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/home")
            client.close()
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["events"], [])

    def test_home_is_404_when_v116_is_disabled(self) -> None:
        with patch.dict(os.environ, {
            "DATABASE_PATH": str(Path(self.temp_dir.name) / "disabled-home.sqlite"),
            "PLATFORM_MARKET_WORKSPACE_V113_ENABLED": "true",
            "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED": "false",
        }, clear=False):
            client = TestClient(create_app(static_dir=self.static_dir))
            response = client.get("/api/v1/market-workspace/home")
            client.close()
        self.assertEqual(response.status_code, 404)


if __name__ == "__main__":
    unittest.main()

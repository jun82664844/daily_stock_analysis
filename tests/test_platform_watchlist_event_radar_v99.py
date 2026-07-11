# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest
import os
import tempfile
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


def _row(
    stock_code: str,
    *,
    change_percent: float | None,
    current_price: float | None = 100.0,
    ma20: float | None = 98.0,
    volume_change_percent: float | None = 25.0,
    status: str = "ok",
    freshness: str = "fresh",
) -> dict:
    return {
        "stock_code": stock_code,
        "stock_name": f"{stock_code} name",
        "market": "us",
        "route_lane": "us_market_data",
        "current_price": current_price,
        "change_percent": change_percent,
        "ma5": 99.0,
        "ma20": ma20,
        "price_change_5d": 3.0,
        "price_change_20d": 8.0,
        "volume_change_percent": volume_change_percent,
        "volume_signal": "price_volume_confirmed",
        "signal_score": 72,
        "updated_at": "2026-07-11T09:30:00",
        "freshness": freshness,
        "degradation_status": "ok" if status == "ok" else "degraded",
        "warning_codes": [] if status == "ok" else ["history_stale"],
        "ai_used": False,
        "status": status,
    }


class _WatchlistStub:
    def __init__(self, rows: list[dict], total: int | None = None) -> None:
        self.rows = rows
        self.total = len(rows) if total is None else total
        self.refresh_limits: list[int] = []

    def list_items(self, user_id: int) -> dict:
        return {"user_id": user_id, "items": [], "total": self.total, "ai_used": False}

    def refresh(self, user_id: int, *, limit: int = 20) -> dict:
        self.refresh_limits.append(limit)
        visible = self.rows[:limit]
        return {
            "user_id": user_id,
            "requested": len(visible),
            "refreshed": len(visible),
            "degraded": sum(1 for item in visible if item["status"] != "ok"),
            "items": visible,
            "ai_used": False,
        }


class _IntelligenceStub:
    def __init__(self, by_symbol: dict[str, list[dict]] | None = None) -> None:
        self.by_symbol = by_symbol or {}

    def list_items(self, **filters: object) -> dict:
        symbol = str(filters.get("scope_value") or "")
        items = self.by_symbol.get(symbol, [])
        return {"items": items, "total": len(items), "page": 1, "page_size": 5}


class PlatformWatchlistEventRadarV99TestCase(unittest.TestCase):
    def test_free_and_paid_plans_use_same_shape_but_different_processing_limits(self) -> None:
        from src.platform_watchlist_radar import PlatformWatchlistRadarService

        rows = [_row(f"S{index}", change_percent=float(index)) for index in range(20)]
        free_watchlist = _WatchlistStub(rows, total=20)
        free = PlatformWatchlistRadarService(
            watchlist_service=free_watchlist,
            intelligence_service=_IntelligenceStub(),
        ).build(user_id=7, plan="free")

        pro_watchlist = _WatchlistStub(rows, total=20)
        pro = PlatformWatchlistRadarService(
            watchlist_service=pro_watchlist,
            intelligence_service=_IntelligenceStub(),
        ).build(user_id=8, plan="pro")

        self.assertEqual(free_watchlist.refresh_limits, [10])
        self.assertEqual(pro_watchlist.refresh_limits, [50])
        self.assertEqual(free["visible_limit"], 10)
        self.assertEqual(free["processed"], 10)
        self.assertEqual(free["hidden_count"], 10)
        self.assertEqual(free["total_watchlist"], 20)
        self.assertEqual(pro["processed"], 20)
        self.assertEqual(pro["hidden_count"], 0)
        self.assertEqual(set(free) - {"items", "events", "summary"}, set(pro) - {"items", "events", "summary"})
        self.assertFalse(free["ai_used"])
        self.assertFalse(pro["ai_used"])

    def test_radar_orders_material_changes_and_builds_no_ai_alert_suggestions(self) -> None:
        from src.platform_watchlist_radar import PlatformWatchlistRadarService

        rows = [
            _row("CALM", change_percent=0.2, volume_change_percent=3.0),
            _row("DROP", change_percent=-7.5, current_price=90.0, ma20=100.0, volume_change_percent=55.0),
            _row("RISE", change_percent=5.2, current_price=110.0, ma20=100.0, volume_change_percent=42.0),
            _row("STALE", change_percent=None, status="degraded", freshness="stale"),
        ]
        result = PlatformWatchlistRadarService(
            watchlist_service=_WatchlistStub(rows),
            intelligence_service=_IntelligenceStub(),
        ).build(user_id=9, plan="free")

        self.assertEqual(result["summary"]["strongest"]["stock_code"], "RISE")
        self.assertEqual(result["summary"]["weakest"]["stock_code"], "DROP")
        self.assertGreaterEqual(result["summary"]["risk_count"], 2)
        self.assertEqual(result["events"][0]["stock_code"], "DROP")
        self.assertEqual(result["events"][0]["type"], "price_move")
        drop = next(item for item in result["items"] if item["stock_code"] == "DROP")
        self.assertIn("price_move", {event["type"] for event in drop["events"]})
        self.assertIn("trend_position", {event["type"] for event in drop["events"]})
        self.assertIn("volume_change", {event["type"] for event in drop["events"]})
        self.assertIn("ma20_cross", {item["type"] for item in drop["suggested_alerts"]})
        self.assertTrue(all(event["ai_used"] is False for event in result["events"]))

    def test_only_traceable_persisted_intelligence_is_exposed_as_source_event(self) -> None:
        from src.platform_watchlist_radar import PlatformWatchlistRadarService

        intelligence = _IntelligenceStub(
            {
                "AAPL": [
                    {
                        "title": "Placeholder without link",
                        "summary": "not traceable",
                        "url": "",
                        "source_name": "placeholder",
                        "published_at": "2026-07-11T08:00:00",
                    },
                    {
                        "title": "Apple files a traceable update",
                        "summary": "Official filing summary",
                        "url": "https://example.com/filing/1",
                        "source_name": "SEC feed",
                        "published_at": "2026-07-11T08:30:00",
                    },
                ]
            }
        )
        result = PlatformWatchlistRadarService(
            watchlist_service=_WatchlistStub([_row("AAPL", change_percent=1.0)]),
            intelligence_service=intelligence,
        ).build(user_id=10, plan="free")

        source_events = [event for event in result["events"] if event["type"] == "source_update"]
        self.assertEqual(len(source_events), 1)
        self.assertEqual(source_events[0]["title"], "Apple files a traceable update")
        self.assertEqual(source_events[0]["source_url"], "https://example.com/filing/1")
        self.assertEqual(result["summary"]["source_event_count"], 1)
        self.assertNotIn("Placeholder without link", str(result))

    def test_intelligence_failure_degrades_without_breaking_market_radar(self) -> None:
        from src.platform_watchlist_radar import PlatformWatchlistRadarService

        class BrokenIntelligence:
            def list_items(self, **filters: object) -> dict:
                raise RuntimeError("feed unavailable with sk-secret-never-return")

        result = PlatformWatchlistRadarService(
            watchlist_service=_WatchlistStub([_row("AAPL", change_percent=3.0)]),
            intelligence_service=BrokenIntelligence(),
        ).build(user_id=11, plan="free")

        self.assertEqual(result["processed"], 1)
        self.assertEqual(result["summary"]["source_event_count"], 0)
        self.assertIn("source_unavailable", result["items"][0]["source_status"])
        self.assertNotIn("sk-secret", str(result))


class PlatformWatchlistEventRadarV99ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-watchlist-radar-v99.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _register(self, email: str) -> int:
        response = self.client.post(
            "/api/v1/platform/register",
            json={"email": email, "password": "password123"},
        )
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_radar_endpoint_requires_login_and_uses_current_user_plan(self) -> None:
        anonymous = TestClient(create_app(static_dir=self.static_dir))
        try:
            self.assertEqual(anonymous.get("/api/v1/platform/watchlist/radar").status_code, 401)
        finally:
            anonymous.close()

        user_id = self._register("radar-v99@example.com")
        self.assertEqual(
            self.client.post("/api/v1/platform/watchlist", json={"stock_code": "AAPL"}).status_code,
            200,
        )
        snapshot = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "quote": {
                "current_price": 210.0,
                "change_percent": 3.5,
                "freshness": "fresh",
                "update_time": "2026-07-11T09:30:00",
            },
            "indicators": {
                "ma5": 207.0,
                "ma20": 202.0,
                "price_change_5d": 4.0,
                "price_change_20d": 8.0,
                "volume_change_vs_ma5": 35.0,
                "volume_price_signal": "price_volume_confirmed",
            },
            "intelligence": {"signal_score": {"score": 78}},
            "route": {"data_source_lane": "us_market_data"},
            "warnings": [],
            "degradation": {"status": "ok"},
            "diagnostics": {"route_lane": "us_market_data"},
            "ai_used": False,
        }
        with (
            patch("src.platform_watchlist.BasicQueryService.get_snapshot", return_value=snapshot),
            patch("src.platform_watchlist_radar.IntelligenceService.list_items", return_value={"items": [], "total": 0}),
        ):
            response = self.client.get("/api/v1/platform/watchlist/radar")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["user_id"], user_id)
        self.assertEqual(body["plan"], "free")
        self.assertEqual(body["processed"], 1)
        self.assertEqual(body["items"][0]["stock_code"], "AAPL")
        self.assertEqual(body["items"][0]["ma20"], 202.0)
        self.assertFalse(body["ai_used"])
        self.assertNotIn("api_key", str(body).lower())


if __name__ == "__main__":
    unittest.main()

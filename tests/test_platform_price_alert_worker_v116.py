# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from collections import Counter
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.platform_watchlist_automation import PlatformWatchlistAutomationService
from src.storage import DatabaseManager


def _quote(price: float, *, freshness: str = "fresh", source: str = "unit_quote") -> dict:
    return {
        "stock_code": "AAPL",
        "quote": {
            "current_price": price,
            "freshness": freshness,
            "source": source,
            "updated_at": "2026-07-13T01:30:00+00:00",
        },
        "ai_used": False,
    }


class PlatformPriceAlertWorkerV116TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "price-alert-v116.sqlite")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(os.environ, {"DATABASE_PATH": self.db_path}, clear=False)
        self.env_patch.start()
        self.db = DatabaseManager.get_instance()
        accounts = PlatformAccountService(self.db)
        self.user_a = accounts.create_user("v116-a@example.com", "password123")
        self.user_b = accounts.create_user("v116-b@example.com", "password123")

    def tearDown(self) -> None:
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _save(self, user_id: int, rule_type: str = "price_above", threshold: float = 200.0) -> int:
        result = PlatformWatchlistAutomationService(db_manager=self.db).save_rule(
            user_id=user_id,
            plan="free",
            stock_code="AAPL",
            rule_type=rule_type,
            threshold=threshold,
        )
        return int(next(item["id"] for item in result["items"] if item["rule_type"] == rule_type))

    def test_first_observation_sets_baseline_without_trigger(self) -> None:
        from src.services.platform_price_alert_worker import PlatformPriceAlertWorker

        self._save(self.user_a.id)
        worker = PlatformPriceAlertWorker(db_manager=self.db, quote_loader=lambda _symbol: _quote(199.0))

        self.assertEqual(
            worker.run_once(),
            {"loaded": 1, "observed": 1, "triggered": 0, "degraded": 0, "failed": 0},
        )
        rule = PlatformWatchlistAutomationService(db_manager=self.db).list_rules(self.user_a.id)["items"][0]
        self.assertEqual(rule["last_observed_value"], 199.0)
        self.assertEqual(PlatformWatchlistAutomationService(db_manager=self.db).list_alert_events(self.user_a.id)["total"], 0)

    def test_default_quote_loader_reuses_service_with_configured_timeout(self) -> None:
        from src.services.platform_price_alert_worker import PlatformPriceAlertWorker

        query_service = unittest.mock.Mock()
        query_service.get_quote_card.return_value = _quote(199.0)
        with patch(
            "src.services.platform_price_alert_worker.BasicQueryService",
            return_value=query_service,
        ) as service_class:
            worker = PlatformPriceAlertWorker(
                db_manager=self.db,
                quote_timeout_seconds=2.5,
            )
            worker.quote_loader("AAPL")
            worker.quote_loader("MSFT")

        service_class.assert_called_once_with(fetch_timeout_seconds=2.5)
        self.assertEqual(query_service.get_quote_card.call_count, 2)

    def test_price_above_triggers_only_on_cross_and_not_while_remaining_above(self) -> None:
        from src.services.platform_price_alert_worker import PlatformPriceAlertWorker

        self._save(self.user_a.id)
        prices = iter((_quote(199.0), _quote(200.5), _quote(201.0)))
        worker = PlatformPriceAlertWorker(db_manager=self.db, quote_loader=lambda _symbol: next(prices))

        self.assertEqual(worker.run_once()["triggered"], 0)
        self.assertEqual(worker.run_once()["triggered"], 1)
        self.assertEqual(worker.run_once()["triggered"], 0)
        events = PlatformWatchlistAutomationService(db_manager=self.db).list_alert_events(self.user_a.id)
        self.assertEqual(events["total"], 1)
        self.assertEqual(events["items"][0]["direction"], "above")

    def test_price_below_crosses_down_and_stale_quote_never_replaces_baseline(self) -> None:
        from src.services.platform_price_alert_worker import PlatformPriceAlertWorker

        self._save(self.user_a.id, "price_below", 180.0)
        prices = iter((_quote(181.0), _quote(175.0, freshness="stale"), _quote(179.5)))
        worker = PlatformPriceAlertWorker(db_manager=self.db, quote_loader=lambda _symbol: next(prices))

        self.assertEqual(worker.run_once()["triggered"], 0)
        stale_stats = worker.run_once()
        self.assertEqual(stale_stats["degraded"], 1)
        self.assertEqual(worker.run_once()["triggered"], 1)
        event = PlatformWatchlistAutomationService(db_manager=self.db).list_alert_events(self.user_a.id)["items"][0]
        self.assertEqual(event["direction"], "below")

    def test_same_symbol_loads_once_and_events_remain_private(self) -> None:
        from src.services.platform_price_alert_worker import PlatformPriceAlertWorker

        self._save(self.user_a.id)
        self._save(self.user_b.id)
        calls: Counter[str] = Counter()
        price = {"value": 199.0}

        def load(symbol: str) -> dict:
            calls[symbol] += 1
            return _quote(price["value"])

        worker = PlatformPriceAlertWorker(db_manager=self.db, quote_loader=load)
        worker.run_once()
        price["value"] = 201.0
        stats = worker.run_once()

        self.assertEqual(calls["AAPL"], 2)
        self.assertEqual(stats["triggered"], 2)
        service = PlatformWatchlistAutomationService(db_manager=self.db)
        events_a = service.list_alert_events(self.user_a.id)
        events_b = service.list_alert_events(self.user_b.id)
        self.assertEqual(events_a["total"], 1)
        self.assertEqual(events_b["total"], 1)
        self.assertNotEqual(events_a["items"][0]["id"], events_b["items"][0]["id"])
        self.assertFalse(service.mark_alert_event_read(self.user_a.id, events_b["items"][0]["id"]))
        self.assertTrue(service.mark_alert_event_read(self.user_a.id, events_a["items"][0]["id"]))
        self.assertEqual(service.list_alert_events(self.user_a.id)["unread"], 0)
        self.assertEqual(service.list_alert_events(self.user_b.id)["unread"], 1)


class PlatformPriceAlertEventsApiV116TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "price-alert-api-v116.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(os.environ, {
            "DATABASE_PATH": self.db_path,
            "PLATFORM_USER_AUTH_ENABLED": "true",
            "ADMIN_AUTH_ENABLED": "true",
            "PLATFORM_CSRF_ENABLED": "false",
            "PLATFORM_RATE_LIMIT_ENABLED": "false",
        }, clear=False)
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def _register_and_trigger(self, email: str) -> tuple[int, int]:
        response = self.client.post("/api/v1/platform/register", json={"email": email, "password": "password123"})
        self.assertEqual(response.status_code, 200)
        user_id = int(response.json()["user"]["id"])
        self.client.post("/api/v1/platform/watchlist/alert-rules", json={
            "stockCode": "AAPL", "ruleType": "price_above", "threshold": 200.0,
        })
        from src.services.platform_price_alert_worker import PlatformPriceAlertWorker
        prices = iter((_quote(199.0), _quote(201.0)))
        worker = PlatformPriceAlertWorker(
            db_manager=DatabaseManager.get_instance(),
            quote_loader=lambda _symbol: next(prices),
        )
        worker.run_once()
        worker.run_once()
        event_id = PlatformWatchlistAutomationService().list_alert_events(user_id)["items"][0]["id"]
        return user_id, int(event_id)

    def test_alert_event_feed_and_read_operations_are_private(self) -> None:
        user_a, event_a = self._register_and_trigger("v116-api-a@example.com")
        feed_a = self.client.get("/api/v1/platform/watchlist/alert-events")
        self.assertEqual(feed_a.status_code, 200)
        self.assertEqual(feed_a.json()["user_id"], user_a)
        self.assertEqual(feed_a.json()["unread"], 1)

        _user_b, event_b = self._register_and_trigger("v116-api-b@example.com")
        self.assertEqual(self.client.post(f"/api/v1/platform/watchlist/alert-events/{event_a}/read").status_code, 404)
        own = self.client.post(f"/api/v1/platform/watchlist/alert-events/{event_b}/read")
        self.assertEqual(own.status_code, 200)
        self.assertEqual(own.json()["unread"], 0)

    def test_mark_all_only_updates_current_user_events(self) -> None:
        _user_a, _event_a = self._register_and_trigger("v116-api-all-a@example.com")
        user_b, _event_b = self._register_and_trigger("v116-api-all-b@example.com")
        response = self.client.post("/api/v1/platform/watchlist/alert-events/read-all")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["user_id"], user_b)
        self.assertEqual(response.json()["unread"], 0)


if __name__ == "__main__":
    unittest.main()

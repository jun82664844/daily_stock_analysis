# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


def _radar(price: float, *, source_update: bool = False, degraded: bool = False) -> dict:
    events = [
        {
            "stock_code": "AAPL",
            "type": "trend_position",
            "severity": "info",
            "direction": "above" if price >= 100 else "below",
            "value": price,
            "reference_value": 100.0,
            "warning_codes": [],
            "ai_used": False,
        }
    ]
    if source_update:
        events.append(
            {
                "stock_code": "AAPL",
                "type": "source_update",
                "severity": "info",
                "direction": "new",
                "title": "Traceable filing",
                "source_name": "Official feed",
                "source_url": "https://example.com/filing/100",
                "occurred_at": "2026-07-11T10:00:00Z",
                "warning_codes": [],
                "ai_used": False,
            }
        )
    if degraded:
        events.append(
            {
                "stock_code": "AAPL",
                "type": "data_quality",
                "severity": "warning",
                "direction": "degraded",
                "warning_codes": ["stale_quote"],
                "ai_used": False,
            }
        )
    item = {
        "stock_code": "AAPL",
        "stock_name": "Apple Inc.",
        "market": "us",
        "route_lane": "us_market_data",
        "current_price": price,
        "change_percent": 2.5,
        "ma5": 99.0,
        "ma20": 100.0,
        "volume_change_percent": 35.0,
        "signal_score": 72,
        "freshness": "stale" if degraded else "fresh",
        "degradation_status": "degraded" if degraded else "ok",
        "warning_codes": ["stale_quote"] if degraded else [],
        "ai_used": False,
        "status": "degraded" if degraded else "ok",
        "source_status": "available" if source_update else "no_traceable_source",
        "research_brief": {
            "state": "risk_review" if degraded else "strong_confirmation",
            "priority_score": 82,
            "data_confidence": "low" if degraded else "high",
            "evidence_codes": ["stale_data" if degraded else "usable_data"],
            "next_watch": {"type": "refresh_data" if degraded else "hold_above_ma20", "value": None if degraded else 100.0},
            "invalidation": {"type": "fresh_data_restored" if degraded else "lose_ma20", "value": None if degraded else 100.0},
            "ai_used": False,
        },
        "events": events,
        "suggested_alerts": [],
    }
    return {
        "user_id": 0,
        "plan": "free",
        "visible_limit": 10,
        "total_watchlist": 1,
        "processed": 1,
        "hidden_count": 0,
        "degraded": 1 if degraded else 0,
        "summary": {
            "strongest": {"stock_code": "AAPL", "stock_name": "Apple Inc.", "change_percent": 2.5},
            "weakest": {"stock_code": "AAPL", "stock_name": "Apple Inc.", "change_percent": 2.5},
            "event_count": len(events),
            "risk_count": 1 if degraded else 0,
            "source_event_count": 1 if source_update else 0,
        },
        "daily_digest": {
            "strong_confirmation": [] if degraded else [{
                "stock_code": "AAPL",
                "stock_name": "Apple Inc.",
                "market": "us",
                "state": "strong_confirmation",
                "priority_score": 82,
                "change_percent": 2.5,
                "signal_score": 72,
                "data_confidence": "high",
            }],
            "risk_review": [{
                "stock_code": "AAPL",
                "stock_name": "Apple Inc.",
                "market": "us",
                "state": "risk_review",
                "priority_score": 82,
                "change_percent": 2.5,
                "signal_score": 72,
                "data_confidence": "low",
            }] if degraded else [],
            "wait_for_confirmation": [],
            "data_health": {"fresh": 0 if degraded else 1, "cached": 0, "stale": 1 if degraded else 0, "unavailable": 0},
            "upgrade_boundary": "same_research_flow_better_sources_and_automation",
            "ai_used": False,
        },
        "items": [item],
        "events": events,
        "generated_at": "2026-07-11T10:00:00Z",
        "ai_used": False,
        "analysis_boundary": "information_only_not_investment_advice",
    }


class _RadarSequence:
    def __init__(self, payloads: list[dict]) -> None:
        self.payloads = list(payloads)

    def build(self, *, user_id: int, plan: str) -> dict:
        payload = dict(self.payloads.pop(0))
        payload["user_id"] = user_id
        payload["plan"] = plan
        return payload


class _SlowSameRadar:
    def build(self, *, user_id: int, plan: str) -> dict:
        time.sleep(0.12)
        payload = _radar(101.0, source_update=True)
        payload["user_id"] = user_id
        payload["plan"] = plan
        return payload


class PlatformWatchlistAlertLoopV100TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "watchlist-alert-v100.sqlite")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(os.environ, {"DATABASE_PATH": self.db_path}, clear=False)
        self.env_patch.start()
        self.db = DatabaseManager.get_instance()
        accounts = PlatformAccountService(self.db)
        self.user_a = accounts.create_user("v100-a@example.com", "password123")
        self.user_b = accounts.create_user("v100-b@example.com", "password123")

    def tearDown(self) -> None:
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_free_rule_limit_and_user_isolation(self) -> None:
        from src.platform_watchlist_automation import AlertRuleLimitExceeded, PlatformWatchlistAutomationService

        service = PlatformWatchlistAutomationService(db_manager=self.db, radar_service=_RadarSequence([]))
        for index, rule_type in enumerate(("price_move", "volume_change", "source_update"), start=1):
            result = service.save_rule(
                user_id=self.user_a.id,
                plan="free",
                stock_code="AAPL",
                rule_type=rule_type,
                threshold=3.0 if index < 3 else None,
            )
            self.assertEqual(result["total"], index)

        with self.assertRaises(AlertRuleLimitExceeded):
            service.save_rule(
                user_id=self.user_a.id,
                plan="free",
                stock_code="AAPL",
                rule_type="data_quality",
                threshold=None,
            )

        self.assertEqual(service.list_rules(self.user_b.id)["items"], [])
        self.assertEqual(service.list_rules(self.user_a.id)["limit"], 3)

    def test_first_run_sets_baseline_and_second_run_triggers_real_ma20_cross(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        service = PlatformWatchlistAutomationService(
            db_manager=self.db,
            radar_service=_RadarSequence([_radar(99.0), _radar(101.0)]),
        )
        service.save_rule(
            user_id=self.user_a.id,
            plan="free",
            stock_code="AAPL",
            rule_type="ma20_cross",
            threshold=None,
            reference_value=100.0,
        )

        first = service.run_and_save(user_id=self.user_a.id, plan="free")
        second = service.run_and_save(user_id=self.user_a.id, plan="free")

        self.assertEqual(first["triggered_alerts"], [])
        self.assertEqual(len(second["triggered_alerts"]), 1)
        self.assertEqual(second["triggered_alerts"][0]["rule_type"], "ma20_cross")
        self.assertEqual(second["triggered_alerts"][0]["direction"], "above")
        history = service.list_history(self.user_a.id, limit=7)
        self.assertEqual(history["total"], 2)
        self.assertEqual(history["items"][0]["triggered_count"], 1)
        self.assertEqual(service.list_history(self.user_b.id, limit=7)["items"], [])

    def test_source_and_data_quality_rules_trigger_only_from_current_user_run(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        PlatformAccountService(self.db).set_user_plan(self.user_a.id, "pro")
        service = PlatformWatchlistAutomationService(
            db_manager=self.db,
            radar_service=_RadarSequence([_radar(101.0, source_update=True, degraded=True)]),
        )
        service.save_rule(user_id=self.user_a.id, plan="pro", stock_code="AAPL", rule_type="source_update")
        service.save_rule(user_id=self.user_a.id, plan="pro", stock_code="AAPL", rule_type="data_quality")

        result = service.run_and_save(user_id=self.user_a.id, plan="pro")

        self.assertEqual({item["rule_type"] for item in result["triggered_alerts"]}, {"source_update", "data_quality"})
        self.assertNotIn("sk-", str(result))
        self.assertEqual(service.list_rules(self.user_a.id)["limit"], 50)

    def test_identical_source_update_triggers_only_once_across_saved_runs(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        service = PlatformWatchlistAutomationService(
            db_manager=self.db,
            radar_service=_RadarSequence([
                _radar(101.0, source_update=True),
                _radar(101.0, source_update=True),
            ]),
        )
        service.save_rule(user_id=self.user_a.id, plan="free", stock_code="AAPL", rule_type="source_update")

        first = service.run_and_save(user_id=self.user_a.id, plan="free")
        second = service.run_and_save(user_id=self.user_a.id, plan="free")

        self.assertEqual(len(first["triggered_alerts"]), 1)
        self.assertEqual(second["triggered_alerts"], [])

    def test_concurrent_runs_for_one_user_serialize_source_deduplication(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        service = PlatformWatchlistAutomationService(db_manager=self.db, radar_service=_SlowSameRadar())
        service.save_rule(user_id=self.user_a.id, plan="free", stock_code="AAPL", rule_type="source_update")

        with ThreadPoolExecutor(max_workers=2) as executor:
            results = list(executor.map(
                lambda _: service.run_and_save(user_id=self.user_a.id, plan="free"),
                range(2),
            ))

        self.assertEqual(sorted(len(result["triggered_alerts"]) for result in results), [0, 1])
        self.assertEqual(service.list_history(self.user_a.id)["total"], 2)

    def test_downgraded_plan_limits_visible_and_executed_rules(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        PlatformAccountService(self.db).set_user_plan(self.user_a.id, "pro")
        service = PlatformWatchlistAutomationService(
            db_manager=self.db,
            radar_service=_RadarSequence([_radar(101.0, source_update=True, degraded=True)]),
        )
        service.save_rule(user_id=self.user_a.id, plan="pro", stock_code="AAPL", rule_type="price_move", threshold=2.0)
        service.save_rule(user_id=self.user_a.id, plan="pro", stock_code="AAPL", rule_type="volume_change", threshold=30.0)
        service.save_rule(user_id=self.user_a.id, plan="pro", stock_code="AAPL", rule_type="source_update")
        service.save_rule(user_id=self.user_a.id, plan="pro", stock_code="AAPL", rule_type="data_quality")
        PlatformAccountService(self.db).set_user_plan(self.user_a.id, "free")

        visible = service.list_rules(self.user_a.id, plan="free")
        run = service.run_and_save(user_id=self.user_a.id, plan="free")

        self.assertEqual(visible["total"], 3)
        self.assertEqual(len(run["triggered_alerts"]), 3)

    def test_non_finite_rule_values_are_rejected(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        service = PlatformWatchlistAutomationService(db_manager=self.db, radar_service=_RadarSequence([]))
        with self.assertRaises(ValueError):
            service.save_rule(
                user_id=self.user_a.id,
                plan="free",
                stock_code="AAPL",
                rule_type="price_move",
                threshold=float("nan"),
            )
        with self.assertRaises(ValueError):
            service.save_rule(
                user_id=self.user_a.id,
                plan="free",
                stock_code="AAPL",
                rule_type="ma20_cross",
                reference_value=float("inf"),
            )

    def test_delete_rule_cannot_cross_user_boundary(self) -> None:
        from src.platform_watchlist_automation import PlatformWatchlistAutomationService

        service = PlatformWatchlistAutomationService(db_manager=self.db, radar_service=_RadarSequence([]))
        created = service.save_rule(
            user_id=self.user_a.id,
            plan="free",
            stock_code="AAPL",
            rule_type="price_move",
            threshold=3.0,
        )["items"][0]

        self.assertFalse(service.delete_rule(user_id=self.user_b.id, rule_id=created["id"]))
        self.assertTrue(service.delete_rule(user_id=self.user_a.id, rule_id=created["id"]))
        self.assertEqual(service.list_rules(self.user_a.id)["items"], [])
        with self.db.get_session() as session:
            from src.storage import PlatformWatchlistAlertRule

            preserved = session.get(PlatformWatchlistAlertRule, created["id"])
            self.assertIsNotNone(preserved)
            self.assertFalse(preserved.enabled)

    def test_delete_triggered_rule_preserves_the_historical_event(self) -> None:
        from sqlalchemy import select

        from src.platform_watchlist_automation import PlatformWatchlistAutomationService
        from src.storage import PlatformWatchlistAlertEvent, PlatformWatchlistAlertRule

        service = PlatformWatchlistAutomationService(
            db_manager=self.db,
            radar_service=_RadarSequence([_radar(101.0)]),
        )
        rule = service.save_rule(
            user_id=self.user_a.id,
            plan="free",
            stock_code="AAPL",
            rule_type="price_move",
            threshold=2.0,
        )["items"][0]
        service.run_and_save(user_id=self.user_a.id, plan="free")

        self.assertTrue(service.delete_rule(user_id=self.user_a.id, rule_id=rule["id"]))
        with self.db.get_session() as session:
            event = session.execute(select(PlatformWatchlistAlertEvent)).scalars().one()
            preserved_rule = session.execute(select(PlatformWatchlistAlertRule)).scalars().one()

        self.assertEqual(event.rule_id, rule["id"])
        self.assertEqual(preserved_rule.id, rule["id"])
        self.assertFalse(preserved_rule.enabled)
        self.assertEqual(service.list_rules(self.user_a.id)["items"], [])


class PlatformWatchlistAlertLoopV100ApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "watchlist-alert-api-v100.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "PLATFORM_USER_AUTH_ENABLED": "true",
                "ADMIN_AUTH_ENABLED": "true",
                "PLATFORM_CSRF_ENABLED": "false",
                "PLATFORM_RATE_LIMIT_ENABLED": "false",
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
        response = self.client.post("/api/v1/platform/register", json={"email": email, "password": "password123"})
        self.assertEqual(response.status_code, 200)
        return int(response.json()["user"]["id"])

    def test_private_alert_rule_run_and_history_api(self) -> None:
        user_a = self._register("v100-api-a@example.com")
        created = self.client.post(
            "/api/v1/platform/watchlist/alert-rules",
            json={"stockCode": "AAPL", "ruleType": "price_move", "threshold": 2.0},
        )
        self.assertEqual(created.status_code, 200)
        self.assertEqual(created.json()["total"], 1)
        rule_id = int(created.json()["items"][0]["id"])

        with patch("src.platform_watchlist_radar.PlatformWatchlistRadarService.build", return_value=_radar(101.0)):
            run = self.client.post("/api/v1/platform/watchlist/radar/run")
        self.assertEqual(run.status_code, 200)
        self.assertEqual(run.json()["user_id"], user_a)
        self.assertEqual(run.json()["triggered_alerts"][0]["rule_type"], "price_move")

        history = self.client.get("/api/v1/platform/watchlist/radar/history")
        self.assertEqual(history.status_code, 200)
        self.assertEqual(history.json()["total"], 1)
        self.assertEqual(history.json()["items"][0]["triggered_count"], 1)

        user_b = self._register("v100-api-b@example.com")
        self.assertNotEqual(user_a, user_b)
        self.assertEqual(self.client.get("/api/v1/platform/watchlist/alert-rules").json()["items"], [])
        self.assertEqual(self.client.get("/api/v1/platform/watchlist/radar/history").json()["items"], [])
        self.assertEqual(self.client.delete(f"/api/v1/platform/watchlist/alert-rules/{rule_id}").status_code, 404)

    def test_delete_rule_uses_the_write_rate_limit(self) -> None:
        from fastapi.responses import JSONResponse

        self._register("v100-api-limit@example.com")
        created = self.client.post(
            "/api/v1/platform/watchlist/alert-rules",
            json={"stockCode": "AAPL", "ruleType": "price_move", "threshold": 2.0},
        )
        rule_id = int(created.json()["items"][0]["id"])
        with patch(
            "api.v1.endpoints.platform.check_platform_rate_limit",
            return_value=JSONResponse(status_code=429, content={"error": "rate_limited"}),
        ) as limiter:
            response = self.client.delete(f"/api/v1/platform/watchlist/alert-rules/{rule_id}")

        self.assertEqual(response.status_code, 429)
        limiter.assert_called_once()


if __name__ == "__main__":
    unittest.main()

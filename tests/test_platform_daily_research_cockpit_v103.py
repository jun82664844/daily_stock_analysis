# -*- coding: utf-8 -*-
from __future__ import annotations

import unittest


def _row(
    stock_code: str,
    *,
    change_percent: float = 0.5,
    current_price: float = 100.0,
    ma20: float = 100.0,
    volume_change_percent: float = 0.0,
    signal_score: int = 50,
    freshness: str = "fresh",
    status: str = "ok",
    warning_codes: list[str] | None = None,
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
        "price_change_5d": 1.0,
        "price_change_20d": 2.0,
        "volume_change_percent": volume_change_percent,
        "volume_signal": "price_volume_confirmed",
        "signal_score": signal_score,
        "updated_at": "2026-07-11T10:00:00Z",
        "freshness": freshness,
        "degradation_status": "ok" if status == "ok" else "degraded",
        "warning_codes": list(warning_codes or []),
        "ai_used": False,
        "status": status,
    }


class _WatchlistStub:
    def __init__(self, rows: list[dict]) -> None:
        self.rows = rows

    def list_items(self, user_id: int) -> dict:
        return {"user_id": user_id, "items": [], "total": len(self.rows), "ai_used": False}

    def refresh(self, user_id: int, *, limit: int = 20) -> dict:
        items = self.rows[:limit]
        return {
            "user_id": user_id,
            "requested": len(items),
            "refreshed": len(items),
            "degraded": sum(1 for item in items if item["status"] != "ok"),
            "items": items,
            "ai_used": False,
        }


class _NoSourceIntelligence:
    def list_items(self, **filters: object) -> dict:
        return {"items": [], "total": 0}


class PlatformDailyResearchCockpitV103TestCase(unittest.TestCase):
    def _build(self, rows: list[dict]) -> dict:
        from src.platform_watchlist_radar import PlatformWatchlistRadarService

        return PlatformWatchlistRadarService(
            watchlist_service=_WatchlistStub(rows),
            intelligence_service=_NoSourceIntelligence(),
        ).build(user_id=103, plan="free")

    def test_classifies_strong_risk_and_wait_states_with_structured_briefs(self) -> None:
        result = self._build([
            _row("STRONG", change_percent=3.2, current_price=112, ma20=100, volume_change_percent=68, signal_score=82),
            _row("RISK", change_percent=-4.1, current_price=88, ma20=100, volume_change_percent=54, signal_score=38),
            _row("WAIT", change_percent=0.3, current_price=101, ma20=100, volume_change_percent=4, signal_score=56),
        ])

        by_code = {item["stock_code"]: item for item in result["items"]}
        self.assertEqual(by_code["STRONG"]["research_brief"]["state"], "strong_confirmation")
        self.assertEqual(by_code["RISK"]["research_brief"]["state"], "risk_review")
        self.assertEqual(by_code["WAIT"]["research_brief"]["state"], "wait_for_confirmation")

        strong = by_code["STRONG"]["research_brief"]
        self.assertIn("price_above_ma20", strong["evidence_codes"])
        self.assertIn("volume_expanded", strong["evidence_codes"])
        self.assertEqual(strong["next_watch"]["type"], "hold_above_ma20")
        self.assertEqual(strong["invalidation"]["type"], "lose_ma20")
        self.assertEqual(strong["data_confidence"], "high")
        self.assertFalse(result["ai_used"])

    def test_stale_or_degraded_data_is_low_confidence_and_never_strong(self) -> None:
        result = self._build([
            _row(
                "STALE",
                change_percent=8.0,
                current_price=120,
                ma20=100,
                volume_change_percent=90,
                signal_score=95,
                freshness="stale",
                status="degraded",
                warning_codes=["quote_stale"],
            )
        ])

        brief = result["items"][0]["research_brief"]
        self.assertEqual(brief["state"], "risk_review")
        self.assertEqual(brief["data_confidence"], "low")
        self.assertEqual(brief["next_watch"]["type"], "refresh_data")
        self.assertIn("stale_data", brief["evidence_codes"])
        self.assertEqual(result["daily_digest"]["data_health"]["stale"], 1)

    def test_daily_digest_limits_each_ranked_group_to_three_symbols(self) -> None:
        rows = [
            _row(
                f"S{index}",
                change_percent=2.0 + index,
                current_price=110 + index,
                ma20=100,
                volume_change_percent=30 + index,
                signal_score=70 + index,
            )
            for index in range(6)
        ]
        result = self._build(rows)

        digest = result["daily_digest"]
        self.assertEqual(len(digest["strong_confirmation"]), 3)
        self.assertEqual(digest["strong_confirmation"][0]["stock_code"], "S5")
        self.assertEqual(digest["strong_confirmation"][0]["state"], "strong_confirmation")
        self.assertEqual(digest["data_health"], {"fresh": 6, "cached": 0, "stale": 0, "unavailable": 0})
        self.assertFalse(digest["ai_used"])

    def test_digest_keeps_same_research_shape_for_free_and_paid_plans(self) -> None:
        from src.platform_watchlist_radar import PlatformWatchlistRadarService

        rows = [_row("AAPL", current_price=105, ma20=100, volume_change_percent=35, signal_score=75)]
        free = self._build(rows)
        paid = PlatformWatchlistRadarService(
            watchlist_service=_WatchlistStub(rows),
            intelligence_service=_NoSourceIntelligence(),
        ).build(user_id=104, plan="pro")

        self.assertEqual(set(free["daily_digest"]), set(paid["daily_digest"]))
        self.assertEqual(set(free["items"][0]["research_brief"]), set(paid["items"][0]["research_brief"]))
        self.assertEqual(free["daily_digest"]["upgrade_boundary"], "same_research_flow_better_sources_and_automation")

    def test_platform_response_schema_preserves_daily_digest_and_item_brief(self) -> None:
        from api.v1.schemas.platform import PlatformWatchlistRadarResponse

        result = self._build([
            _row("AAPL", change_percent=2.5, current_price=110, ma20=100, volume_change_percent=40, signal_score=78)
        ])
        payload = PlatformWatchlistRadarResponse.model_validate(result).model_dump()

        self.assertEqual(payload["daily_digest"]["strong_confirmation"][0]["stock_code"], "AAPL")
        self.assertEqual(payload["items"][0]["research_brief"]["state"], "strong_confirmation")
        self.assertFalse(payload["daily_digest"]["ai_used"])


if __name__ == "__main__":
    unittest.main()

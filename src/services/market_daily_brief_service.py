# -*- coding: utf-8 -*-
"""Private, no-AI watchlist brief for V113."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from src.platform_watchlist import PlatformWatchlistService


class MarketDailyBriefService:
    def __init__(self, watchlist_service: Optional[PlatformWatchlistService] = None) -> None:
        self.watchlist_service = watchlist_service or PlatformWatchlistService()

    def build(self, user_id: int, *, limit: int = 20) -> Dict[str, Any]:
        watchlist = self.watchlist_service.list_items(int(user_id))
        listed = list(watchlist.get("items") or [])[: max(1, min(int(limit), 20))]
        now = datetime.now(timezone.utc).isoformat()
        if not listed:
            return {
                "user_id": int(user_id),
                "as_of": now,
                "items": [],
                "empty_action": "add_watchlist",
                "warnings": [],
                "ai_used": False,
                "informational_only": True,
            }

        refreshed = self.watchlist_service.refresh(int(user_id), limit=len(listed))
        items = []
        warnings = []
        for row in refreshed.get("items") or []:
            freshness = str(row.get("freshness") or "unavailable")
            if freshness not in {"fresh", "cached", "stale", "unavailable"}:
                freshness = "unavailable"
            warning_codes = [str(code) for code in row.get("warning_codes") or []]
            if row.get("status") != "ok":
                warnings.append(f"{row.get('stock_code')}:data_degraded")
            items.append({
                "symbol": str(row.get("stock_code") or ""),
                "name": str(row.get("stock_name") or row.get("stock_code") or ""),
                "market": str(row.get("market") or "unknown"),
                "current_price": row.get("current_price"),
                "change_percent": row.get("change_percent"),
                "freshness": freshness,
                "status": str(row.get("status") or "unavailable"),
                "warning_codes": warning_codes,
            })
        return {
            "user_id": int(user_id),
            "as_of": now,
            "items": items,
            "empty_action": None,
            "warnings": warnings,
            "ai_used": False,
            "informational_only": True,
        }

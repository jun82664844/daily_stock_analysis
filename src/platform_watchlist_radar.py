# -*- coding: utf-8 -*-
"""User-scoped, no-AI watchlist event radar."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional
from urllib.parse import urlparse

from src.platform_watchlist import PlatformWatchlistService
from src.services.intelligence_service import IntelligenceService


_PAID_PLANS = {"pro", "premium", "enterprise"}
_SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}
_TYPE_ORDER = {
    "price_move": 0,
    "data_quality": 1,
    "source_update": 2,
    "volume_change": 3,
    "trend_position": 4,
}


class PlatformWatchlistRadarService:
    """Build a deterministic daily review without calling AI or live feeds."""

    def __init__(
        self,
        *,
        watchlist_service: Optional[PlatformWatchlistService] = None,
        intelligence_service: Optional[IntelligenceService] = None,
    ) -> None:
        self.watchlist_service = watchlist_service or PlatformWatchlistService()
        self.intelligence_service = intelligence_service or IntelligenceService()

    def build(self, *, user_id: int, plan: str) -> Dict[str, Any]:
        normalized_plan = str(plan or "free").lower()
        visible_limit = 50 if normalized_plan in _PAID_PLANS else 10
        watchlist = self.watchlist_service.list_items(int(user_id))
        total_watchlist = max(0, int(watchlist.get("total") or 0))
        refreshed = self.watchlist_service.refresh(int(user_id), limit=visible_limit)

        items: List[Dict[str, Any]] = []
        events: List[Dict[str, Any]] = []
        for source_row in refreshed.get("items") or []:
            row = dict(source_row)
            item_events = self._market_events(row)
            source_events, source_status = self._source_events(row)
            item_events.extend(source_events)
            suggestions = self._suggested_alerts(row)
            item_events.sort(key=self._event_sort_key)
            row.update(
                {
                    "events": item_events,
                    "suggested_alerts": suggestions,
                    "source_status": source_status,
                    "ai_used": bool(row.get("ai_used")),
                }
            )
            items.append(row)
            events.extend(item_events)

        events.sort(key=self._event_sort_key)
        priced_items = [item for item in items if self._number(item.get("change_percent")) is not None]
        strongest = max(priced_items, key=lambda item: self._number(item.get("change_percent")) or 0.0, default=None)
        weakest = min(priced_items, key=lambda item: self._number(item.get("change_percent")) or 0.0, default=None)
        risk_count = sum(
            1
            for item in items
            if item.get("status") != "ok"
            or any(event.get("severity") in {"critical", "warning"} for event in item.get("events") or [])
        )
        source_event_count = sum(1 for event in events if event.get("type") == "source_update")
        processed = len(items)
        return {
            "user_id": int(user_id),
            "plan": normalized_plan,
            "visible_limit": visible_limit,
            "total_watchlist": total_watchlist,
            "processed": processed,
            "hidden_count": max(0, total_watchlist - processed),
            "degraded": int(refreshed.get("degraded") or 0),
            "summary": {
                "strongest": self._summary_item(strongest),
                "weakest": self._summary_item(weakest),
                "event_count": len(events),
                "risk_count": risk_count,
                "source_event_count": source_event_count,
            },
            "items": items,
            "events": events,
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "ai_used": bool(refreshed.get("ai_used")),
            "analysis_boundary": "information_only_not_investment_advice",
        }

    def _market_events(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        stock_code = str(row.get("stock_code") or "")
        change = self._number(row.get("change_percent"))
        current_price = self._number(row.get("current_price"))
        ma20 = self._number(row.get("ma20"))
        volume_change = self._number(row.get("volume_change_percent"))
        occurred_at = row.get("updated_at")
        events: List[Dict[str, Any]] = []

        if change is not None and abs(change) >= 2:
            events.append(
                self._event(
                    stock_code=stock_code,
                    event_type="price_move",
                    severity="critical" if abs(change) >= 5 else "warning",
                    direction="up" if change > 0 else "down",
                    value=change,
                    occurred_at=occurred_at,
                )
            )
        if current_price is not None and ma20 is not None:
            events.append(
                self._event(
                    stock_code=stock_code,
                    event_type="trend_position",
                    severity="info" if current_price >= ma20 else "warning",
                    direction="above" if current_price >= ma20 else "below",
                    value=current_price,
                    reference_value=ma20,
                    occurred_at=occurred_at,
                )
            )
        if volume_change is not None and abs(volume_change) >= 20:
            events.append(
                self._event(
                    stock_code=stock_code,
                    event_type="volume_change",
                    severity="warning" if abs(volume_change) >= 50 else "info",
                    direction="expanded" if volume_change > 0 else "contracted",
                    value=volume_change,
                    occurred_at=occurred_at,
                )
            )
        freshness = str(row.get("freshness") or "unavailable").lower()
        warning_codes = [str(value) for value in row.get("warning_codes") or []]
        if row.get("status") != "ok" or freshness in {"stale", "unavailable"} or warning_codes:
            events.append(
                self._event(
                    stock_code=stock_code,
                    event_type="data_quality",
                    severity="warning",
                    direction="degraded",
                    occurred_at=occurred_at,
                    warning_codes=warning_codes,
                )
            )
        return events

    def _source_events(self, row: Dict[str, Any]) -> tuple[List[Dict[str, Any]], str]:
        stock_code = str(row.get("stock_code") or "")
        try:
            payload = self.intelligence_service.list_items(
                scope_type="stock",
                scope_value=stock_code,
                published_days=7,
                page=1,
                page_size=5,
            )
        except Exception:
            return [], "source_unavailable"

        events: List[Dict[str, Any]] = []
        for item in payload.get("items") or []:
            if not isinstance(item, dict) or not self._is_traceable_source(item):
                continue
            source_name = str(item.get("source_name") or item.get("source") or "").strip()
            events.append(
                self._event(
                    stock_code=stock_code,
                    event_type="source_update",
                    severity="info",
                    direction="new",
                    title=str(item.get("title") or "").strip(),
                    summary=str(item.get("summary") or "").strip() or None,
                    source_name=source_name,
                    source_url=str(item.get("url") or "").strip(),
                    occurred_at=item.get("published_at") or item.get("fetched_at"),
                )
            )
        return events, "available" if events else "no_traceable_source"

    def _suggested_alerts(self, row: Dict[str, Any]) -> List[Dict[str, Any]]:
        stock_code = str(row.get("stock_code") or "")
        suggestions: List[Dict[str, Any]] = [
            {
                "stock_code": stock_code,
                "type": "price_move",
                "threshold": 3.0,
                "reference_value": None,
                "ai_used": False,
            }
        ]
        ma20 = self._number(row.get("ma20"))
        if ma20 is not None:
            suggestions.append(
                {
                    "stock_code": stock_code,
                    "type": "ma20_cross",
                    "threshold": None,
                    "reference_value": ma20,
                    "ai_used": False,
                }
            )
        if self._number(row.get("volume_change_percent")) is not None:
            suggestions.append(
                {
                    "stock_code": stock_code,
                    "type": "volume_change",
                    "threshold": 30.0,
                    "reference_value": None,
                    "ai_used": False,
                }
            )
        return suggestions

    @staticmethod
    def _event(
        *,
        stock_code: str,
        event_type: str,
        severity: str,
        direction: str,
        value: Optional[float] = None,
        reference_value: Optional[float] = None,
        title: Optional[str] = None,
        summary: Optional[str] = None,
        source_name: Optional[str] = None,
        source_url: Optional[str] = None,
        occurred_at: Any = None,
        warning_codes: Optional[Iterable[str]] = None,
    ) -> Dict[str, Any]:
        return {
            "stock_code": stock_code,
            "type": event_type,
            "severity": severity,
            "direction": direction,
            "value": value,
            "reference_value": reference_value,
            "title": title,
            "summary": summary,
            "source_name": source_name,
            "source_url": source_url,
            "occurred_at": occurred_at,
            "warning_codes": list(warning_codes or []),
            "ai_used": False,
        }

    @staticmethod
    def _is_traceable_source(item: Dict[str, Any]) -> bool:
        title = str(item.get("title") or "").strip()
        url = str(item.get("url") or "").strip()
        source = str(item.get("source_name") or item.get("source") or "").strip()
        occurred_at = item.get("published_at") or item.get("fetched_at")
        parsed = urlparse(url)
        return bool(title and source and occurred_at and parsed.scheme in {"http", "https"} and parsed.netloc)

    @staticmethod
    def _number(value: Any) -> Optional[float]:
        try:
            return None if value is None else float(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _summary_item(item: Optional[Dict[str, Any]]) -> Optional[Dict[str, Any]]:
        if item is None:
            return None
        return {
            "stock_code": item.get("stock_code"),
            "stock_name": item.get("stock_name"),
            "change_percent": item.get("change_percent"),
        }

    @staticmethod
    def _event_sort_key(event: Dict[str, Any]) -> tuple[int, float, int, str]:
        severity = _SEVERITY_ORDER.get(str(event.get("severity")), 9)
        value = PlatformWatchlistRadarService._number(event.get("value"))
        magnitude = -abs(value) if value is not None else 0.0
        event_type = _TYPE_ORDER.get(str(event.get("type")), 9)
        return severity, magnitude, event_type, str(event.get("stock_code") or "")

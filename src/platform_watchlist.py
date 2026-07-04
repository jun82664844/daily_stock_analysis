# -*- coding: utf-8 -*-
"""Per-user platform watchlist and no-AI refresh helpers."""

from __future__ import annotations

import re
from typing import Any, Dict, List, Optional

from sqlalchemy import and_, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert

from data_provider.base import normalize_stock_code
from src.services.basic_query_service import BasicQueryService
from src.services.stock_code_utils import normalize_crypto_symbol
from src.storage import DatabaseManager, PlatformWatchlistItem, utc_naive_now


_STOCK_CODE_RE = re.compile(
    r"^(?:\d{6}"
    r"|(?:SH|SZ|BJ)\d{6}"
    r"|\d{6}\.(?:SH|SZ|SS|BJ)"
    r"|\d{1,5}\.HK"
    r"|HK\d{1,5}"
    r"|\d{5}"
    r"|[A-Z]{1,5}(?:\.(?:US|[A-Z]))?"
    r")$",
    re.IGNORECASE,
)


class PlatformWatchlistService:
    """Store and refresh a watchlist scoped to one platform user."""

    def __init__(
        self,
        db_manager: Optional[DatabaseManager] = None,
        basic_query_service: Optional[BasicQueryService] = None,
    ) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.basic_query_service = basic_query_service or BasicQueryService()

    def list_items(self, user_id: int) -> Dict[str, Any]:
        items = self._list_rows(user_id)
        return {
            "user_id": int(user_id),
            "items": [self._item_payload(item) for item in items],
            "total": len(items),
            "ai_used": False,
        }

    def add_item(self, user_id: int, stock_code: str) -> Dict[str, Any]:
        normalized = self.normalize_stock_code(stock_code)
        market = self.market_for_code(normalized)
        now = utc_naive_now()
        with self.db.session_scope() as session:
            stmt = sqlite_insert(PlatformWatchlistItem).values(
                user_id=int(user_id),
                stock_code=normalized,
                input_code=(stock_code or "").strip(),
                market=market,
                created_at=now,
                updated_at=now,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["user_id", "stock_code"],
                set_={
                    "input_code": (stock_code or "").strip(),
                    "market": market,
                    "updated_at": now,
                },
            )
            session.execute(stmt)
        return self.list_items(user_id)

    def remove_item(self, user_id: int, stock_code: str) -> Dict[str, Any]:
        normalized = self.normalize_stock_code(stock_code)
        with self.db.session_scope() as session:
            row = session.execute(
                select(PlatformWatchlistItem).where(
                    and_(
                        PlatformWatchlistItem.user_id == int(user_id),
                        PlatformWatchlistItem.stock_code == normalized,
                    )
                )
            ).scalars().first()
            if row is not None:
                session.delete(row)
        return self.list_items(user_id)

    def refresh(self, user_id: int, *, limit: int = 20) -> Dict[str, Any]:
        rows = self._list_rows(user_id, limit=limit)
        items: List[Dict[str, Any]] = []
        refreshed = 0
        degraded = 0
        ai_used = False
        for row in rows:
            summary = self._refresh_item(row.stock_code)
            if summary["status"] in {"ok", "degraded"}:
                refreshed += 1
            if summary["status"] != "ok":
                degraded += 1
            ai_used = ai_used or bool(summary.get("ai_used"))
            items.append(summary)
        return {
            "user_id": int(user_id),
            "requested": len(rows),
            "refreshed": refreshed,
            "degraded": degraded,
            "items": items,
            "ai_used": ai_used,
        }

    def _refresh_item(self, stock_code: str) -> Dict[str, Any]:
        try:
            snapshot = self.basic_query_service.get_snapshot(stock_code)
            route = snapshot.get("route") or {}
            quote = snapshot.get("quote") or {}
            degradation = snapshot.get("degradation") or {}
            warnings = snapshot.get("warnings") or []
            diagnostics = snapshot.get("diagnostics") or {}
            status = "degraded" if degradation.get("status") == "degraded" else "ok"
            return {
                "stock_code": str(snapshot.get("stock_code") or stock_code),
                "stock_name": snapshot.get("stock_name"),
                "market": str(snapshot.get("market") or self.market_for_code(stock_code)),
                "route_lane": route.get("data_source_lane") or diagnostics.get("route_lane"),
                "current_price": quote.get("current_price"),
                "change_percent": quote.get("change_percent"),
                "freshness": quote.get("freshness") or "unavailable",
                "degradation_status": degradation.get("status") or status,
                "warning_codes": [str(item.get("code")) for item in warnings if isinstance(item, dict) and item.get("code")],
                "ai_used": bool(snapshot.get("ai_used")) is True,
                "status": status,
            }
        except Exception:
            return {
                "stock_code": stock_code,
                "stock_name": None,
                "market": self.market_for_code(stock_code),
                "route_lane": None,
                "current_price": None,
                "change_percent": None,
                "freshness": "unavailable",
                "degradation_status": "degraded",
                "warning_codes": ["refresh_failed"],
                "ai_used": False,
                "status": "error",
            }

    def _list_rows(self, user_id: int, *, limit: Optional[int] = None) -> List[PlatformWatchlistItem]:
        stmt = (
            select(PlatformWatchlistItem)
            .where(PlatformWatchlistItem.user_id == int(user_id))
            .order_by(PlatformWatchlistItem.created_at.asc(), PlatformWatchlistItem.id.asc())
        )
        if limit is not None:
            stmt = stmt.limit(max(1, min(int(limit), 50)))
        with self.db.get_session() as session:
            rows = session.execute(stmt).scalars().all()
            for row in rows:
                session.expunge(row)
            return list(rows)

    def _item_payload(self, item: PlatformWatchlistItem) -> Dict[str, Any]:
        return {
            "id": int(item.id),
            "stock_code": item.stock_code,
            "input_code": item.input_code,
            "market": item.market,
            "created_at": item.created_at.isoformat() if item.created_at else None,
            "updated_at": item.updated_at.isoformat() if item.updated_at else None,
        }

    @staticmethod
    def normalize_stock_code(stock_code: str) -> str:
        raw = (stock_code or "").strip()
        if not raw:
            raise ValueError("stock_code is required")
        crypto = normalize_crypto_symbol(raw)
        if crypto is not None:
            return crypto
        if not _STOCK_CODE_RE.match(raw):
            raise ValueError(f"invalid stock code: {raw}")
        normalized = normalize_stock_code(raw)
        upper = normalized.upper()
        if re.fullmatch(r"\d{1,5}", upper):
            return f"HK{upper.zfill(5)}"
        return upper

    @staticmethod
    def market_for_code(stock_code: str) -> str:
        upper = (stock_code or "").upper()
        if normalize_crypto_symbol(upper) is not None or upper.endswith("-USD"):
            return "crypto"
        if upper.startswith("HK") or upper.endswith(".HK"):
            return "hk"
        if upper.isdigit() and len(upper) <= 5:
            return "hk"
        if upper.endswith((".SH", ".SZ", ".BJ")) or (upper.isdigit() and len(upper) == 6):
            return "cn"
        return "us"

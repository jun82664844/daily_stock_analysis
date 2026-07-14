# -*- coding: utf-8 -*-
"""Deterministic, no-AI normalization for public market events."""

from __future__ import annotations

import hashlib
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence


MARKETS = ("cn", "hk", "us")
SOURCE_STATUSES = {"fresh", "cached", "stale", "unavailable"}
SECURITY_KEYS = ("indices", "attention", "most_active", "gainers", "losers")
A_SHARE_SYMBOL_PATTERN = re.compile(r"(?<![A-Z0-9])(\d{6})\.(SH|SZ)(?![A-Z])", re.IGNORECASE)
HK_SYMBOL_PATTERN = re.compile(r"(?<![A-Z0-9])(\d{1,5})\.HK(?![A-Z])", re.IGNORECASE)

CATEGORY_RULES = (
    ("trading_status", ("停牌", "复牌", "退市", "涨停", "跌停", "halt", "suspended", "delist")),
    ("earnings", ("业绩", "财报", "净利润", "盈利", "亏损", "预增", "预亏", "results", "earnings", "profit", "revenue", "guidance")),
    ("macro", ("央行", "逆回购", "美联储", "利率", "工厂订单", "耐用品订单", "cpi", "gdp", "非农", "通胀", "inflation", "federal reserve", "central bank", "factory orders", "payroll")),
    ("dividend", ("分红", "派息", "股息", "回购", "dividend", "buyback", "repurchase")),
    ("announcement", ("公告", "披露", "filing", "sec filing", "announcement")),
    ("corporate", ("收购", "并购", "订单", "合作", "融资", "merger", "acquisition", "contract", "partnership", "financing")),
)


class PublicMarketEventService:
    """Build structured events from data already loaded for the public home."""

    def __init__(self, *, max_events_per_market: int = 8, max_events_total: int = 24) -> None:
        self.max_events_per_market = max(1, min(int(max_events_per_market), 20))
        self.max_events_total = max(1, min(int(max_events_total), 60))

    def build(self, markets: Sequence[Dict[str, Any]], as_of: str) -> List[Dict[str, Any]]:
        normalized: List[tuple[int, Dict[str, Any]]] = []
        seen: set[tuple[str, str, str]] = set()
        market_counts = {market: 0 for market in MARKETS}
        ordinal = 0

        by_market = {
            str(section.get("market") or "").lower(): section
            for section in markets
            if isinstance(section, dict)
        }
        for market in MARKETS:
            section = by_market.get(market)
            if not section:
                continue
            securities = self._securities(section)
            for headline in section.get("headlines") or []:
                if not isinstance(headline, dict):
                    continue
                title = str(headline.get("title") or "").strip()
                if not title:
                    continue
                explicit_symbol, explicit_market = self._explicit_exchange_symbol(title)
                event_market = explicit_market or market
                if market_counts[event_market] >= self.max_events_per_market:
                    continue
                published_at = str(headline.get("published_at") or "").strip()
                event_time = published_at or as_of
                time_kind = "published" if published_at else "retrieved"
                dedupe_key = (event_market, title.casefold(), event_time)
                if dedupe_key in seen:
                    continue
                seen.add(dedupe_key)
                linked_symbol, linked_name = self._linked_security(title, securities)
                symbol = explicit_symbol or linked_symbol
                name = linked_name if linked_symbol and (not explicit_symbol or linked_symbol.casefold() == explicit_symbol.casefold()) else None
                event = {
                    "event_id": self._event_id(event_market, title, event_time),
                    "market": event_market,
                    "category": self._category(title),
                    "title": title,
                    "summary": self._optional_text(headline.get("summary")),
                    "symbol": symbol,
                    "name": name,
                    "event_time": event_time,
                    "time_kind": time_kind,
                    "publisher": self._optional_text(headline.get("publisher")),
                    "url": self._optional_text(headline.get("url")),
                    "source_state": self._source_state(headline.get("source_state")),
                    "classification_source": "keyword_rules",
                }
                normalized.append((ordinal, event))
                ordinal += 1
                market_counts[event_market] += 1

        normalized.sort(key=self._sort_key, reverse=True)
        return [event for _, event in normalized[: self.max_events_total]]

    @staticmethod
    def _category(title: str) -> str:
        lowered = title.casefold()
        for category, keywords in CATEGORY_RULES:
            if any(keyword in lowered for keyword in keywords):
                return category
        return "market"

    @staticmethod
    def _securities(section: Dict[str, Any]) -> List[Dict[str, str]]:
        securities: List[Dict[str, str]] = []
        seen: set[str] = set()
        for key in SECURITY_KEYS:
            for item in section.get(key) or []:
                if not isinstance(item, dict):
                    continue
                symbol = str(item.get("symbol") or "").strip()
                name = str(item.get("name") or "").strip()
                if not symbol or symbol.casefold() in seen:
                    continue
                seen.add(symbol.casefold())
                securities.append({"symbol": symbol, "name": name})
        return securities

    @staticmethod
    def _linked_security(title: str, securities: Iterable[Dict[str, str]]) -> tuple[Optional[str], Optional[str]]:
        for security in securities:
            symbol = security["symbol"]
            name = security["name"]
            if PublicMarketEventService._symbol_in_title(title, symbol) or PublicMarketEventService._name_in_title(title, name):
                return symbol, name or None
        return None, None

    @staticmethod
    def _symbol_in_title(title: str, symbol: str) -> bool:
        core = symbol.split(".", 1)[0].strip()
        if not core:
            return False
        escaped = re.escape(symbol)
        if len(core) <= 2 and core.isalpha():
            return bool(re.search(rf"(?<![A-Z0-9])\${re.escape(core)}(?![A-Z0-9])", title, re.IGNORECASE))
        return bool(re.search(rf"(?<![A-Z0-9]){escaped}(?![A-Z0-9])", title, re.IGNORECASE))

    @staticmethod
    def _name_in_title(title: str, name: str) -> bool:
        candidate = name.strip()
        if len(candidate) < 2:
            return False
        if any(ord(character) > 127 for character in candidate):
            return candidate.casefold() in title.casefold()
        return bool(re.search(rf"(?<![A-Z0-9]){re.escape(candidate)}(?![A-Z0-9])", title, re.IGNORECASE))

    @staticmethod
    def _explicit_exchange_symbol(title: str) -> tuple[Optional[str], Optional[str]]:
        a_share = A_SHARE_SYMBOL_PATTERN.search(title)
        if a_share:
            return f"{a_share.group(1)}.{a_share.group(2).upper()}", "cn"
        hk_share = HK_SYMBOL_PATTERN.search(title)
        if hk_share:
            return f"{hk_share.group(1)}.HK", "hk"
        return None, None

    @staticmethod
    def _event_id(market: str, title: str, event_time: str) -> str:
        raw = f"{market}\n{title}\n{event_time}".encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:20]

    @staticmethod
    def _source_state(value: Any) -> Dict[str, Any]:
        payload = dict(value) if isinstance(value, dict) else {}
        status = str(payload.get("status") or "unavailable").lower()
        result: Dict[str, Any] = {
            "source": str(payload.get("source") or "public_market_news"),
            "status": status if status in SOURCE_STATUSES else "unavailable",
        }
        for key in ("observed_at", "fetched_at", "delay_seconds", "warning_code"):
            if payload.get(key) is not None:
                result[key] = payload[key]
        return result

    @staticmethod
    def _optional_text(value: Any) -> Optional[str]:
        text = str(value or "").strip()
        return text or None

    @staticmethod
    def _sort_key(item: tuple[int, Dict[str, Any]]) -> tuple[int, float, int]:
        ordinal, event = item
        is_published = 1 if event["time_kind"] == "published" else 0
        raw_time = str(event.get("event_time") or "")
        try:
            parsed = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            timestamp = parsed.timestamp()
        except (TypeError, ValueError, OverflowError):
            timestamp = 0.0
        return is_published, timestamp, -ordinal

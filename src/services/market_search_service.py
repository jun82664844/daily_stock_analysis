# -*- coding: utf-8 -*-
"""Deterministic three-market symbol search for V113."""

from __future__ import annotations

import re
from typing import Dict, List, Sequence


_UNSAFE_QUERY = re.compile(r"[<>]|(?:javascript:)|(?:script)", re.IGNORECASE)


_CATALOG: tuple[Dict[str, str], ...] = (
    {"symbol": "600519.SH", "name": "贵州茅台", "market": "cn", "exchange": "SSE", "currency": "CNY"},
    {"symbol": "000001.SZ", "name": "平安银行", "market": "cn", "exchange": "SZSE", "currency": "CNY"},
    {"symbol": "300750.SZ", "name": "宁德时代", "market": "cn", "exchange": "SZSE", "currency": "CNY"},
    {"symbol": "0700.HK", "name": "腾讯控股", "market": "hk", "exchange": "HKEX", "currency": "HKD"},
    {"symbol": "9988.HK", "name": "阿里巴巴-W", "market": "hk", "exchange": "HKEX", "currency": "HKD"},
    {"symbol": "3690.HK", "name": "美团-W", "market": "hk", "exchange": "HKEX", "currency": "HKD"},
    {"symbol": "AAPL", "name": "Apple Inc.", "market": "us", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "MSFT", "name": "Microsoft Corporation", "market": "us", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "NVDA", "name": "NVIDIA Corporation", "market": "us", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "TSLA", "name": "Tesla, Inc.", "market": "us", "exchange": "NASDAQ", "currency": "USD"},
    {"symbol": "AMZN", "name": "Amazon.com, Inc.", "market": "us", "exchange": "NASDAQ", "currency": "USD"},
)


class MarketSearchService:
    def __init__(self, catalog: Sequence[Dict[str, str]] | None = None) -> None:
        self.catalog = tuple(dict(item) for item in (catalog or _CATALOG))

    def search(self, query: str, markets: Sequence[str], limit: int = 8) -> List[Dict[str, object]]:
        text = (query or "").strip()
        if not text or len(text) > 64 or _UNSAFE_QUERY.search(text):
            raise ValueError("invalid_search_query")
        allowed_markets = [market for market in markets if market in {"cn", "hk", "us"}]
        if not allowed_markets:
            raise ValueError("invalid_market")
        capped_limit = max(1, min(int(limit), 20))
        folded = text.casefold()
        results: List[Dict[str, object]] = []
        for item in self.catalog:
            if item["market"] not in allowed_markets:
                continue
            symbol = item["symbol"]
            name = item["name"]
            symbol_folded = symbol.casefold()
            name_folded = name.casefold()
            if symbol_folded == folded:
                match_type = "exact_symbol"
                rank = 0
            elif symbol_folded.startswith(folded):
                match_type = "symbol_prefix"
                rank = 1
            elif name_folded.startswith(folded):
                match_type = "name_prefix"
                rank = 2
            elif folded in name_folded:
                match_type = "name_contains"
                rank = 3
            else:
                continue
            results.append({
                **item,
                "match_type": match_type,
                "_rank": rank,
                "source_state": {
                    "source": "dsa_symbol_catalog",
                    "status": "cached",
                    "warning_code": None,
                },
            })
        results.sort(key=lambda item: (int(item["_rank"]), str(item["market"]), str(item["symbol"])))
        for item in results:
            item.pop("_rank", None)
        return results[:capped_limit]

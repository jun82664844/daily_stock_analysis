# -*- coding: utf-8 -*-
"""Read-only local operations snapshot for quick-query market sources."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Iterable

from src.services.basic_query_service import BasicQueryService, MarketRoute
from src.services.market_source_health import MarketSourceHealthRegistry, default_market_source_health


_MARKET_ROUTE_PROBES: tuple[str, ...] = ("600519", "AAPL", "HK00700", "BTC-USD")


def build_market_source_ops_snapshot(
    *,
    query_service: BasicQueryService | None = None,
    source_health: MarketSourceHealthRegistry | None = None,
) -> dict[str, Any]:
    """Return a local-only, no-AI source priority and health snapshot."""

    service = query_service or BasicQueryService()
    health = source_health or default_market_source_health
    lanes = [_lane_payload(service._resolve_route(symbol), health=health) for symbol in _MARKET_ROUTE_PROBES]
    degraded = sum(
        1
        for lane in lanes
        for item in [*lane["quote_sources"], *lane["history_sources"]]
        if item.get("status") in {"cooling_down", "slow"}
    )
    return {
        "mode": "local_only",
        "ai_used": False,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "cache": {
            "mode": getattr(service.cache, "persistent_mode", "memory"),
            "storage": getattr(service.cache, "storage_label", "memory"),
        },
        "summary": {
            "lane_count": len(lanes),
            "source_count": sum(len(lane["quote_sources"]) + len(lane["history_sources"]) for lane in lanes),
            "degraded_source_count": degraded,
        },
        "lanes": lanes,
    }


def recover_market_sources(
    *,
    query_service: BasicQueryService | None = None,
    source_health: MarketSourceHealthRegistry | None = None,
    market: str | None = None,
    sources: Iterable[str] | None = None,
    symbols: Iterable[str] | None = None,
    prewarm: bool = True,
) -> dict[str, Any]:
    """Reset local source-health cooldown state and optionally prewarm no-AI snapshots."""

    service = query_service or BasicQueryService()
    health = source_health or default_market_source_health
    selected_sources = _select_recovery_sources(service, market=market, sources=sources)
    reset_sources = health.reset_sources(selected_sources)
    prewarm_summary = (
        service.prewarm_snapshots(symbols if symbols is not None else _MARKET_ROUTE_PROBES)
        if prewarm
        else {
            "requested": 0,
            "warmed": 0,
            "degraded": 0,
            "symbols": [],
            "results": {},
            "elapsed_ms": 0,
            "ai_used": False,
        }
    )
    return {
        "mode": "local_only",
        "action": "reset_source_health",
        "market": _normalize_market_filter(market),
        "reset_sources": reset_sources,
        "reset_count": len(reset_sources),
        "prewarm": prewarm_summary,
        "health": build_market_source_ops_snapshot(query_service=service, source_health=health),
        "ai_used": False,
    }


def _lane_payload(route: MarketRoute, *, health: MarketSourceHealthRegistry) -> dict[str, Any]:
    return {
        "market": route.market,
        "channel": route.channel,
        "route_lane": route.data_source_lane,
        "quote_sources": _source_items(route.quote_sources, health=health),
        "history_sources": _source_items(route.history_sources, health=health),
    }


def _source_items(sources: Iterable[str], *, health: MarketSourceHealthRegistry) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for index, source in enumerate(sources, start=1):
        state = dict(health.snapshot(source))
        items.append(
            {
                "source": source,
                "priority_rank": index,
                "status": state.get("status") or "ok",
                "consecutive_failures": int(state.get("consecutive_failures") or 0),
                "last_error": state.get("last_error"),
                "last_latency_ms": state.get("last_latency_ms"),
                "cooldown_remaining_sec": int(state.get("cooldown_remaining_sec") or 0),
            }
        )
    return items


def _select_recovery_sources(
    service: BasicQueryService,
    *,
    market: str | None,
    sources: Iterable[str] | None,
) -> list[str]:
    explicit = [str(source).strip() for source in (sources or []) if str(source).strip()]
    if explicit:
        return _dedupe(explicit)

    market_filter = _normalize_market_filter(market)
    selected: list[str] = []
    for symbol in _MARKET_ROUTE_PROBES:
        route = service._resolve_route(symbol)
        if market_filter != "all" and route.market != market_filter:
            continue
        selected.extend(route.quote_sources)
        selected.extend(route.history_sources)
    return _dedupe(selected)


def _normalize_market_filter(market: str | None) -> str:
    value = str(market or "all").strip().lower()
    if value in {"", "*"}:
        return "all"
    return value


def _dedupe(values: Iterable[str]) -> list[str]:
    result: list[str] = []
    seen: set[str] = set()
    for value in values:
        item = str(value).strip()
        if not item or item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result

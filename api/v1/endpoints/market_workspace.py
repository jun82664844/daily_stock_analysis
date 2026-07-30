# -*- coding: utf-8 -*-
"""V113 native market workspace endpoints."""

from __future__ import annotations

import os
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter, HTTPException, Query, Request

from api.v1.schemas.market_workspace import (
    MarketDailyBriefResponse,
    MarketSearchResponse,
    MarketWorkspaceOverview,
    PublicMarketEventReactionResponse,
    PublicMarketHomeResponse,
    SymbolWorkspaceResponse,
)
from src.platform_accounts import platform_identity_from_request
from src.platform_rate_limit import check_platform_rate_limit
from src.services.market_daily_brief_service import MarketDailyBriefService
from src.services.market_search_service import MarketSearchService
from src.services.public_market_index_service import PublicMarketIndexService
from src.services.public_market_news_service import PublicMarketNewsService
from src.services.public_market_event_reaction_service import (
    PublicMarketEventReactionService,
)
from src.services.public_event_reaction_cache import (
    PublicEventReactionSnapshotStore,
)
from src.services.public_market_calendar_service import PublicMarketCalendarService
from src.services.market_workspace_service import MarketWorkspaceService
from src.services.public_market_home_service import PublicMarketHomeService
from src.services.public_market_ranking_service import PublicMarketRankingService


router = APIRouter()
_public_market_news_service = PublicMarketNewsService()
_public_market_index_service = PublicMarketIndexService()
_workspace_service = MarketWorkspaceService(
    news_loader=_public_market_news_service.load,
    index_loader=_public_market_index_service.load,
)
_public_home_workspace_service = MarketWorkspaceService(
    news_loader=_public_market_news_service.load,
    index_loader=_public_market_index_service.load,
    market_symbols={"cn": (), "hk": (), "us": ()},
)
_search_service = MarketSearchService()
_public_market_ranking_service = PublicMarketRankingService()
_public_market_calendar_service = PublicMarketCalendarService()
_public_home_service = PublicMarketHomeService(
    _public_home_workspace_service,
    ranking_loader=_public_market_ranking_service.load,
    calendar_loader=_public_market_calendar_service.load,
)

_EVENT_REACTION_LOADER_EXECUTOR = ThreadPoolExecutor(
    max_workers=3,
    thread_name_prefix="event-reaction-market",
)
_EVENT_REACTION_DEFAULT_SECTIONS = {
    "cn": {
        "market": "cn",
        "attention": [
            {"symbol": "600519.SH", "name": "贵州茅台", "market": "cn"},
            {"symbol": "000001.SZ", "name": "平安银行", "market": "cn"},
            {"symbol": "300750.SZ", "name": "宁德时代", "market": "cn"},
            {"symbol": "601318.SH", "name": "中国平安", "market": "cn"},
        ],
    },
    "hk": {
        "market": "hk",
        "attention": [
            {"symbol": "0700.HK", "name": "腾讯控股", "market": "hk"},
            {"symbol": "9988.HK", "name": "阿里巴巴-W", "market": "hk"},
            {"symbol": "3690.HK", "name": "美团-W", "market": "hk"},
            {"symbol": "1810.HK", "name": "小米集团-W", "market": "hk"},
        ],
    },
    "us": {
        "market": "us",
        "attention": [
            {"symbol": "AAPL", "name": "Apple Inc.", "market": "us"},
            {"symbol": "MSFT", "name": "Microsoft", "market": "us"},
            {"symbol": "NVDA", "name": "NVIDIA", "market": "us"},
            {"symbol": "AMZN", "name": "Amazon", "market": "us"},
        ],
    },
}


def _event_history_v138_enabled() -> bool:
    return os.getenv(
        "PLATFORM_PUBLIC_EVENT_HISTORY_V138_ENABLED",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}


def _event_history_past_days() -> int:
    if not _event_history_v138_enabled():
        return 45
    try:
        configured = int(os.getenv(
            "PLATFORM_PUBLIC_EVENT_HISTORY_V138_PAST_DAYS",
            "180",
        ))
    except ValueError:
        configured = 180
    return max(45, min(configured, 400))


def _load_event_reaction_events():
    as_of = datetime.now(timezone.utc).isoformat()
    event_history_enabled = _event_history_v138_enabled()
    past_days = _event_history_past_days()
    jobs = {
        market: _EVENT_REACTION_LOADER_EXECUTOR.submit(
            _public_market_calendar_service.load,
            [section],
            as_of,
            past_days=past_days,
            future_days=0,
            max_events=24,
            newest_first=True,
            include_historical=True,
            include_observed_history=event_history_enabled,
            fail_on_source_unavailable=True,
        )
        for market, section in _EVENT_REACTION_DEFAULT_SECTIONS.items()
    }
    completed, _ = wait(
        tuple(jobs.values()),
        timeout=max(0.5, _public_market_calendar_service.timeout_seconds + 0.5),
    )
    events = []
    market_sources = []
    status_priority = {"fresh": 3, "cached": 2, "stale": 1, "unavailable": 0}
    for market in ("cn", "hk", "us"):
        future = jobs[market]
        loaded = None
        if future in completed:
            try:
                loaded = list(future.result() or [])
            except Exception:
                loaded = None
        if loaded is None:
            market_sources.append({
                "market": market,
                "status": "unavailable",
                "event_count": 0,
                "observed_at": None,
                "fetched_at": as_of,
                "warning_code": "event_calendar_market_unavailable",
            })
            continue
        events.extend(loaded)
        statuses = [
            str((event.get("source_state") or {}).get("status") or "unavailable")
            for event in loaded
            if isinstance(event, dict)
        ]
        status = (
            max(statuses, key=lambda item: status_priority.get(item, 0))
            if statuses
            else "fresh"
        )
        observed = [
            str(event.get("event_time") or "")
            for event in loaded
            if isinstance(event, dict) and event.get("event_time")
        ]
        market_sources.append({
            "market": market,
            "status": status,
            "event_count": len(loaded),
            "observed_at": max(observed) if observed else None,
            "fetched_at": as_of,
            "warning_code": None,
        })
    return {
        "events": sorted(
            events,
            key=lambda event: str(event.get("event_time") or ""),
            reverse=True,
        )[:72],
        "market_sources": market_sources,
    }


_public_event_reaction_service = PublicMarketEventReactionService(
    event_loader=_load_event_reaction_events,
    snapshot_store=PublicEventReactionSnapshotStore(
        cache_ttl_seconds=max(
            1,
            int(os.getenv(
                "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_CACHE_TTL_SECONDS",
                "900",
            )),
        ),
        stale_ttl_seconds=max(
            900,
            int(os.getenv(
                "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_DISK_STALE_TTL_SECONDS",
                "86400",
            )),
        ),
    ),
)


def _enabled() -> bool:
    return os.getenv("PLATFORM_MARKET_WORKSPACE_V113_ENABLED", "false").strip().lower() in {"1", "true", "yes", "on"}


def _require_enabled() -> None:
    if not _enabled():
        raise HTTPException(status_code=404, detail={"error": "market_workspace_disabled"})


def _require_home_enabled() -> None:
    _require_enabled()
    if os.getenv("PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED", "false").strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(status_code=404, detail={"error": "public_market_home_disabled"})


def _require_event_reactions_enabled() -> None:
    _require_home_enabled()
    if os.getenv(
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED",
        "false",
    ).strip().lower() not in {"1", "true", "yes", "on"}:
        raise HTTPException(
            status_code=404,
            detail={
                "error": "public_event_reactions_disabled",
                "message": "Public event-window observations are disabled.",
            },
        )


def _event_reaction_cache_first_enabled() -> bool:
    return os.getenv(
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_FIRST_ENABLED",
        "false",
    ).strip().lower() in {"1", "true", "yes", "on"}


def prewarm_public_event_reactions() -> bool:
    if not _enabled():
        return False
    if os.getenv(
        "PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED",
        "false",
    ).strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    if os.getenv(
        "PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED",
        "false",
    ).strip().lower() not in {"1", "true", "yes", "on"}:
        return False
    if not _event_reaction_cache_first_enabled():
        return False
    return _public_event_reaction_service.prewarm()


@router.get("/home", response_model=PublicMarketHomeResponse)
def market_home(request: Request):
    _require_home_enabled()
    identity = platform_identity_from_request(request)
    limited = check_platform_rate_limit(request, "market_workspace_home", user_id=identity.user_id if identity else None)
    if limited is not None:
        return limited
    return PublicMarketHomeResponse.model_validate(_public_home_service.build())


@router.get("/event-reactions", response_model=PublicMarketEventReactionResponse)
def market_event_reactions(request: Request):
    _require_event_reactions_enabled()
    limited = check_platform_rate_limit(
        request,
        "market_workspace_event_reactions",
        enforce=True,
    )
    if limited is not None:
        return limited
    try:
        payload = _public_event_reaction_service.build(
            cache_first=_event_reaction_cache_first_enabled(),
        )
        return PublicMarketEventReactionResponse.model_validate(payload)
    except Exception as exc:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "event_reactions_unavailable",
                "message": "Event-window observations are temporarily unavailable.",
            },
        ) from exc


def _markets(value: str) -> List[str]:
    result = [item.strip().lower() for item in (value or "").split(",") if item.strip()]
    if not result or any(item not in {"cn", "hk", "us"} for item in result):
        raise HTTPException(status_code=400, detail={"error": "invalid_market"})
    return list(dict.fromkeys(result))


@router.get("/overview", response_model=MarketWorkspaceOverview)
def market_overview(request: Request, market: str = Query(..., pattern="^(cn|hk|us)$")):
    _require_enabled()
    identity = platform_identity_from_request(request)
    limited = check_platform_rate_limit(request, "market_workspace_overview", user_id=identity.user_id if identity else None)
    if limited is not None:
        return limited
    try:
        return MarketWorkspaceOverview.model_validate(_workspace_service.get_overview(market))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc


@router.get("/search", response_model=MarketSearchResponse)
def market_search(
    request: Request,
    q: str = Query(..., min_length=1, max_length=64),
    markets: str = Query("cn,hk,us"),
    limit: int = Query(8, ge=1, le=20),
):
    _require_enabled()
    identity = platform_identity_from_request(request)
    limited = check_platform_rate_limit(request, "market_workspace_search", user_id=identity.user_id if identity else None)
    if limited is not None:
        return limited
    selected = _markets(markets)
    try:
        items = _search_service.search(q, selected, limit)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail={"error": str(exc)}) from exc
    return MarketSearchResponse(query=q.strip(), markets=selected, items=items, ai_used=False)


@router.get("/symbol/{symbol}", response_model=SymbolWorkspaceResponse)
def symbol_workspace(request: Request, symbol: str):
    _require_enabled()
    if not symbol or len(symbol) > 32 or any(char in symbol for char in "<>/\\"):
        raise HTTPException(status_code=400, detail={"error": "invalid_symbol"})
    identity = platform_identity_from_request(request)
    limited = check_platform_rate_limit(request, "market_workspace_symbol", user_id=identity.user_id if identity else None)
    if limited is not None:
        return limited
    try:
        payload = _workspace_service.get_symbol(symbol, personalization_user_id=identity.user_id if identity else None)
        return SymbolWorkspaceResponse.model_validate(payload)
    except Exception as exc:
        raise HTTPException(status_code=503, detail={"error": "symbol_data_unavailable"}) from exc


@router.get("/daily-brief", response_model=MarketDailyBriefResponse)
def daily_brief(request: Request):
    _require_enabled()
    identity = platform_identity_from_request(request)
    if identity is None:
        raise HTTPException(status_code=401, detail={"error": "platform_login_required"})
    return MarketDailyBriefResponse.model_validate(MarketDailyBriefService().build(identity.user_id))

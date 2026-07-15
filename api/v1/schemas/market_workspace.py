# -*- coding: utf-8 -*-
"""Public, secret-free DTOs for the V113 market workspace."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


SourceStatus = Literal["fresh", "cached", "stale", "unavailable"]
MarketSessionPhase = Literal[
    "premarket",
    "intraday",
    "lunch_break",
    "closing_auction",
    "postmarket",
    "non_trading",
    "unknown",
]
MarketEventCategory = Literal[
    "earnings",
    "announcement",
    "dividend",
    "trading_status",
    "macro",
    "corporate",
    "market",
]
MarketEventTimeKind = Literal["published", "observed", "retrieved", "unknown"]
MarketEventImportance = Literal["high", "medium", "low"]


class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class DataSourceState(StrictModel):
    source: str
    status: SourceStatus
    observed_at: Optional[str] = None
    fetched_at: Optional[str] = None
    delay_seconds: Optional[int] = Field(default=None, ge=0)
    warning_code: Optional[str] = None


class MarketCacheState(StrictModel):
    hit: bool = False
    age_seconds: int = Field(0, ge=0)
    ttl_seconds: int = Field(60, ge=1)


class MarketBreadth(StrictModel):
    advancers: int = Field(0, ge=0)
    decliners: int = Field(0, ge=0)
    unchanged: int = Field(0, ge=0)
    unavailable: bool = False


class MarketSecurityItem(StrictModel):
    symbol: str
    name: str
    market: Literal["cn", "hk", "us"]
    currency: Optional[str] = None
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[float] = None
    turnover: Optional[float] = None
    market_cap: Optional[float] = None
    sector: Optional[str] = None
    trading_session: Optional[Literal["pre", "regular", "post", "closed", "unknown"]] = None
    source_state: DataSourceState


class MarketSectorItem(StrictModel):
    name: str
    market: Literal["cn", "hk", "us"]
    change_percent: Optional[float] = None
    leading_symbol: Optional[str] = None
    leading_name: Optional[str] = None
    leading_change_percent: Optional[float] = None
    source_state: DataSourceState


class MarketHeadline(StrictModel):
    title: str
    summary: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    url: Optional[str] = None
    source_state: DataSourceState


class PublicMarketEventSourceRecord(StrictModel):
    publisher: str
    source: str
    url: Optional[str] = None
    event_time: str
    time_kind: MarketEventTimeKind


class PublicMarketEvent(StrictModel):
    event_id: str
    market: Literal["cn", "hk", "us"]
    category: MarketEventCategory
    title: str
    summary: Optional[str] = None
    symbol: Optional[str] = None
    name: Optional[str] = None
    event_time: str
    time_kind: MarketEventTimeKind
    publisher: Optional[str] = None
    url: Optional[str] = None
    source_state: DataSourceState
    classification_source: Literal["keyword_rules"] = "keyword_rules"
    relevance_score: int = Field(0, ge=0, le=100)
    importance: MarketEventImportance = "low"
    relevance_reasons: List[str] = Field(default_factory=list)
    source_count: int = Field(1, ge=1, le=20)
    source_publishers: List[str] = Field(default_factory=list, max_length=8)
    source_records: List[PublicMarketEventSourceRecord] = Field(default_factory=list, max_length=8)


class MarketWorkspaceOverview(StrictModel):
    market: Literal["cn", "hk", "us"]
    as_of: str
    session_state: Literal["open", "closed", "unknown"] = "unknown"
    session_phase: MarketSessionPhase = "unknown"
    market_local_time: Optional[str] = None
    minutes_to_open: Optional[int] = Field(default=None, ge=0)
    minutes_to_close: Optional[int] = Field(default=None, ge=0)
    session_source: Literal["exchange_calendar", "unavailable"] = "unavailable"
    session_warning_codes: List[str] = Field(default_factory=list)
    indices: List[MarketSecurityItem] = Field(default_factory=list)
    breadth: MarketBreadth
    movers: List[MarketSecurityItem] = Field(default_factory=list)
    heatmap: List[MarketSecurityItem] = Field(default_factory=list)
    headlines: List[MarketHeadline] = Field(default_factory=list)
    sources: List[DataSourceState] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    cache: MarketCacheState
    ai_used: bool = False
    informational_only: bool = True


class PublicMarketHomeSection(StrictModel):
    market: Literal["cn", "hk", "us"]
    session_state: Literal["open", "closed", "unknown"] = "unknown"
    session_phase: MarketSessionPhase = "unknown"
    market_local_time: Optional[str] = None
    minutes_to_open: Optional[int] = Field(default=None, ge=0)
    minutes_to_close: Optional[int] = Field(default=None, ge=0)
    session_source: Literal["exchange_calendar", "unavailable"] = "unavailable"
    session_warning_codes: List[str] = Field(default_factory=list)
    display_mode: Literal["latest_available", "delayed", "realtime"] = "latest_available"
    ranking_scope: Literal["configured_universe", "market_wide", "unavailable"] = "configured_universe"
    selection_basis: str
    indices: List[MarketSecurityItem] = Field(default_factory=list)
    attention: List[MarketSecurityItem] = Field(default_factory=list)
    most_active: List[MarketSecurityItem] = Field(default_factory=list)
    gainers: List[MarketSecurityItem] = Field(default_factory=list)
    losers: List[MarketSecurityItem] = Field(default_factory=list)
    sector_highlights: List[MarketSectorItem] = Field(default_factory=list)
    ranking_cache: MarketCacheState = Field(default_factory=MarketCacheState)
    headlines: List[MarketHeadline] = Field(default_factory=list)
    sources: List[DataSourceState] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)


class PublicMarketHomeResponse(StrictModel):
    as_of: str
    markets: List[PublicMarketHomeSection] = Field(default_factory=list)
    events: List[PublicMarketEvent] = Field(default_factory=list)
    ai_used: bool = False
    informational_only: bool = True


class MarketSearchItem(StrictModel):
    symbol: str
    name: str
    market: Literal["cn", "hk", "us"]
    exchange: Optional[str] = None
    currency: Optional[str] = None
    match_type: Literal["exact_symbol", "symbol_prefix", "name_prefix", "name_contains"]
    source_state: DataSourceState


class MarketSearchResponse(StrictModel):
    query: str
    markets: List[Literal["cn", "hk", "us"]]
    items: List[MarketSearchItem] = Field(default_factory=list)
    ai_used: bool = False


class SymbolWorkspaceResponse(StrictModel):
    symbol: str
    name: str
    market: Literal["cn", "hk", "us"]
    currency: Optional[str] = None
    as_of: Optional[str] = None
    quote: Dict[str, Any] = Field(default_factory=dict)
    history: List[Dict[str, Any]] = Field(default_factory=list)
    indicators: Dict[str, Any] = Field(default_factory=dict)
    profile: Dict[str, Any] = Field(default_factory=dict)
    headlines: List[MarketHeadline] = Field(default_factory=list)
    sources: List[DataSourceState] = Field(default_factory=list)
    warnings: List[str] = Field(default_factory=list)
    personalization: Optional[Dict[str, Any]] = None
    ai_used: bool = False
    informational_only: bool = True


class DailyBriefItem(StrictModel):
    symbol: str
    name: str
    market: str
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    freshness: SourceStatus = "unavailable"
    status: str = "unavailable"
    warning_codes: List[str] = Field(default_factory=list)


class MarketDailyBriefResponse(StrictModel):
    user_id: int
    as_of: str
    items: List[DailyBriefItem] = Field(default_factory=list)
    empty_action: Optional[str] = None
    warnings: List[str] = Field(default_factory=list)
    ai_used: bool = False
    informational_only: bool = True

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
MarketEventTimeKind = Literal["published", "observed", "retrieved", "scheduled", "unknown"]
MarketEventImportance = Literal["high", "medium", "low"]
MarketScheduledEventType = Literal[
    "earnings_release",
    "ex_dividend",
    "stock_split",
    "macro_policy",
]
MarketEventReactionStatus = Literal["available", "partial", "pending", "unavailable"]
MarketEventReactionWindowStatus = Literal["available", "pending", "insufficient_data"]


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


class EventReactionCacheState(MarketCacheState):
    storage: Literal["none", "memory", "disk"] = "none"
    refreshing: bool = False


class EventReactionMarketSource(StrictModel):
    market: Literal["cn", "hk", "us"]
    status: SourceStatus
    event_count: int = Field(0, ge=0, le=72)
    observed_at: Optional[str] = None
    fetched_at: Optional[str] = None
    warning_code: Optional[str] = None


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
    sector: Optional[str] = None
    event_time: str
    time_kind: MarketEventTimeKind
    publisher: Optional[str] = None
    url: Optional[str] = None
    source_state: DataSourceState
    classification_source: Literal[
        "keyword_rules",
        "provider_schedule",
        "provider_event_history",
    ] = "keyword_rules"
    schedule_type: Optional[MarketScheduledEventType] = None
    relevance_score: int = Field(0, ge=0, le=100)
    importance: MarketEventImportance = "low"
    relevance_reasons: List[str] = Field(default_factory=list)
    source_count: int = Field(1, ge=1, le=20)
    source_publishers: List[str] = Field(default_factory=list, max_length=8)
    source_records: List[PublicMarketEventSourceRecord] = Field(default_factory=list, max_length=8)


class MarketEventReactionWindow(StrictModel):
    trading_days: Literal[1, 3, 5, 20]
    status: MarketEventReactionWindowStatus
    observed_date: Optional[str] = None
    symbol_return_percent: Optional[float] = None
    benchmark_return_percent: Optional[float] = None
    relative_return_percent: Optional[float] = None
    volume_ratio: Optional[float] = None


class PublicMarketEventReaction(StrictModel):
    event_id: str
    market: Literal["cn", "hk", "us"]
    title: str
    symbol: str
    name: str
    subject_type: Literal["security", "market_benchmark"]
    event_time: str
    event_time_kind: Literal["scheduled", "observed"] = "scheduled"
    classification_source: Literal[
        "provider_schedule",
        "provider_event_history",
    ] = "provider_schedule"
    schedule_type: Optional[MarketScheduledEventType] = None
    history_symbol: str
    baseline_date: Optional[str] = None
    benchmark_symbol: Optional[str] = None
    benchmark_name: Optional[str] = None
    status: MarketEventReactionStatus
    windows: List[MarketEventReactionWindow] = Field(default_factory=list, max_length=4)
    source_state: DataSourceState
    benchmark_source_state: Optional[DataSourceState] = None
    warning_codes: List[str] = Field(default_factory=list, max_length=8)


class PublicMarketEventReactionResponse(StrictModel):
    as_of: str
    items: List[PublicMarketEventReaction] = Field(default_factory=list, max_length=6)
    market_sources: List[EventReactionMarketSource] = Field(
        default_factory=list,
        max_length=3,
    )
    warnings: List[str] = Field(default_factory=list, max_length=12)
    cache: EventReactionCacheState
    ai_used: bool = False
    informational_only: bool = True


SymbolArchiveEventType = Literal[
    "earnings",
    "dividend",
    "split",
    "buyback",
    "announcement",
]


class PublicSymbolEventArchiveItem(PublicMarketEventReaction):
    event_type: SymbolArchiveEventType
    summary: Optional[str] = None
    publisher: str
    source_url: Optional[str] = None
    event_source_state: DataSourceState


class PublicSymbolEventChartPoint(StrictModel):
    date: str
    symbol_close: float
    benchmark_close: Optional[float] = None
    symbol_change_percent: float
    benchmark_change_percent: Optional[float] = None
    relative_change_percent: Optional[float] = None
    volume: Optional[float] = None


class PublicSymbolEventChart(StrictModel):
    status: Literal["available", "partial", "unavailable"]
    history_symbol: str
    benchmark_symbol: str
    benchmark_name: str
    points: List[PublicSymbolEventChartPoint] = Field(
        default_factory=list,
        max_length=560,
    )
    source_state: DataSourceState
    benchmark_source_state: DataSourceState
    warning_codes: List[str] = Field(default_factory=list, max_length=8)


class PublicSymbolEventComparisonWindow(StrictModel):
    trading_days: Literal[1, 3, 5, 20]
    sample_size: int = Field(ge=0, le=24)
    benchmark_sample_size: int = Field(ge=0, le=24)
    relative_sample_size: int = Field(ge=0, le=24)
    positive_count: int = Field(ge=0, le=24)
    negative_count: int = Field(ge=0, le=24)
    flat_count: int = Field(ge=0, le=24)
    symbol_median_return_percent: Optional[float] = None
    symbol_min_return_percent: Optional[float] = None
    symbol_max_return_percent: Optional[float] = None
    benchmark_median_return_percent: Optional[float] = None
    relative_median_return_percent: Optional[float] = None
    completeness_percent: float = Field(ge=0, le=100)


class PublicSymbolEventComparisonSummary(StrictModel):
    event_type: SymbolArchiveEventType
    event_count: int = Field(ge=1, le=24)
    observed_event_count: int = Field(ge=0, le=24)
    windows: List[PublicSymbolEventComparisonWindow] = Field(
        default_factory=list,
        max_length=4,
    )


class PublicSymbolEventArchiveResponse(StrictModel):
    symbol: str
    name: str
    market: Literal["cn", "hk", "us"]
    months: Literal[6, 12, 24]
    as_of: str
    items: List[PublicSymbolEventArchiveItem] = Field(
        default_factory=list,
        max_length=24,
    )
    chart: PublicSymbolEventChart
    comparison_summaries: List[
        PublicSymbolEventComparisonSummary
    ] = Field(default_factory=list, max_length=5)
    available_event_types: List[SymbolArchiveEventType] = Field(
        default_factory=list,
        max_length=5,
    )
    warnings: List[str] = Field(default_factory=list, max_length=12)
    ai_used: bool = False
    informational_only: bool = True
    causality_disclaimer: bool = True


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

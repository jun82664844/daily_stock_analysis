# -*- coding: utf-8 -*-
"""No-AI basic stock query API schemas."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class BasicQuotePayload(BaseModel):
    """Latest quote facts for the basic no-AI query lane."""

    current_price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    prev_close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    update_time: Optional[str] = None
    source: str = "stock_service"
    freshness: str = Field(..., pattern="^(fresh|cached|stale|unavailable)$")


class BasicProfilePayload(BaseModel):
    """Deterministic company facts for the no-AI query lane."""

    company_name: Optional[str] = None
    sector: Optional[str] = None
    industry: Optional[str] = None
    exchange: Optional[str] = None
    currency: Optional[str] = None
    country: Optional[str] = None
    website: Optional[str] = None
    market_cap: Optional[float] = None
    pe_ratio: Optional[float] = None
    pb_ratio: Optional[float] = None
    dividend_yield: Optional[float] = None
    revenue: Optional[float] = None
    net_profit: Optional[float] = None
    revenue_growth: Optional[float] = None
    earnings_growth: Optional[float] = None
    source: str = "profile_unavailable"
    freshness: str = Field("unavailable", pattern="^(fresh|cached|stale|unavailable)$")


class BasicRoutePayload(BaseModel):
    """Resolved deterministic data lane for a no-AI query."""

    input_code: Optional[str] = None
    normalized_code: str
    market: str
    channel: str
    data_source_lane: str
    quote_sources: List[str] = Field(default_factory=list)
    history_sources: List[str] = Field(default_factory=list)
    profile_sources: List[str] = Field(default_factory=list)
    ai_required: bool = False


class BasicWarningPayload(BaseModel):
    """User-visible degradation warning for the quick query lane."""

    code: str
    severity: str = "warning"
    message: str


class BasicDegradationPayload(BaseModel):
    """Overall degradation state for the quick query lane."""

    status: str = "ok"
    severity: str = "info"
    message: str = "Market data ready"


class BasicTrendPointPayload(BaseModel):
    """One compact historical point for the no-AI mini trend chart."""

    date: Optional[str] = None
    close: float
    volume: Optional[float] = None


class BasicTrendPayload(BaseModel):
    """Compressed deterministic trend data for a free no-AI snapshot."""

    window: int = Field(0, ge=0)
    source: str = "history"
    points: List[BasicTrendPointPayload] = Field(default_factory=list)
    min_close: Optional[float] = None
    max_close: Optional[float] = None
    change_percent: Optional[float] = None


class BasicIntelligenceItemPayload(BaseModel):
    """One deterministic low-cost information item for a free no-AI snapshot."""

    category: str
    title: str
    summary: str
    status: str = Field("available", pattern="^(available|degraded|unavailable)$")
    source: str = "no_ai_quick_snapshot"
    updated_at: Optional[str] = None


class BasicWatchPointPayload(BaseModel):
    """One deterministic next observation point for the free no-AI report."""

    category: str
    title: str
    detail: str
    priority: str = Field("medium", pattern="^(high|medium|low)$")
    source: str = "no_ai_rules"


class BasicComparisonTargetPayload(BaseModel):
    """One deterministic reference target for low-cost comparison context."""

    label: str
    symbol: str
    reason: str
    status: str = "reference_only"
    source: str = "no_ai_route_rules"


class BasicMarketBriefPayload(BaseModel):
    """Market-lane explanation for the free no-AI report."""

    market: str
    title: str
    summary: str
    lane: str
    focus_points: List[str] = Field(default_factory=list)
    deep_unlock: str


class BasicFreeInsightPayload(BaseModel):
    """Structured no-AI insight card for the free query experience."""

    category: str
    title: str
    summary: str
    tone: str = Field("info", pattern="^(positive|neutral|warning|info)$")
    bullets: List[str] = Field(default_factory=list)
    source: str = "no_ai_rules"


class BasicPeerComparisonRowPayload(BaseModel):
    """One no-AI peer or market reference row for the free query view."""

    symbol: str
    label: str
    role: str
    reason: str
    current_signal: str
    compare_next: str
    source: str = "no_ai_route_rules"


class BasicPeerComparisonPayload(BaseModel):
    """Route-based peer and market comparison table for the free query view."""

    title: str
    summary: str
    rows: List[BasicPeerComparisonRowPayload] = Field(default_factory=list)


class BasicSignalScoreComponentPayload(BaseModel):
    """One deterministic component behind the no-AI quick signal score."""

    key: str
    label: str
    score: int = Field(..., ge=0, le=100)
    status: str = Field("neutral", pattern="^(positive|neutral|warning|missing)$")
    detail: str


class BasicSignalScorePayload(BaseModel):
    """Deterministic free-tier signal score without AI or public search."""

    score: int = Field(..., ge=0, le=100)
    label: str
    summary: str
    components: List[BasicSignalScoreComponentPayload] = Field(default_factory=list)
    source: str = "no_ai_rules"
    ai_used: bool = False


class BasicRetentionBriefPayload(BaseModel):
    """Product-facing no-AI summary that helps first-time users keep reading."""

    headline: str
    why_it_matters: str
    support_resistance: str
    next_steps: List[str] = Field(default_factory=list)
    upgrade_hint: str
    boundary: str = "Information analysis only; not investment advice."
    source: str = "no_ai_retention_rules"


class BasicIntelligencePayload(BaseModel):
    """Low-cost information summary that never invokes AI or public search."""

    mode: str = "no_ai_low_cost"
    ai_used: bool = False
    market_brief: Optional[BasicMarketBriefPayload] = None
    free_insights: List[BasicFreeInsightPayload] = Field(default_factory=list)
    peer_comparison: Optional[BasicPeerComparisonPayload] = None
    signal_score: Optional[BasicSignalScorePayload] = None
    retention_brief: Optional[BasicRetentionBriefPayload] = None
    items: List[BasicIntelligenceItemPayload] = Field(default_factory=list)
    watch_points: List[BasicWatchPointPayload] = Field(default_factory=list)
    comparison_targets: List[BasicComparisonTargetPayload] = Field(default_factory=list)
    boundary: str = "Information analysis only; not investment advice."


class BasicQueryDiagnosticsPayload(BaseModel):
    """Timing, cache, and source diagnostics for the no-AI query lane."""

    elapsed_ms: float = Field(..., ge=0)
    quote_elapsed_ms: float = Field(..., ge=0)
    history_elapsed_ms: float = Field(..., ge=0)
    profile_elapsed_ms: float = Field(0, ge=0)
    cache: Dict[str, str] = Field(default_factory=dict)
    sources: Dict[str, str] = Field(default_factory=dict)
    freshness: Dict[str, str] = Field(default_factory=dict)
    timeouts: Dict[str, bool] = Field(default_factory=dict)
    errors: Dict[str, Optional[str]] = Field(default_factory=dict)
    fallback: Dict[str, str] = Field(default_factory=dict)
    source_health: Dict[str, Any] = Field(default_factory=dict)
    persistent_cache: Dict[str, Any] = Field(default_factory=dict)
    refresh: Dict[str, Any] = Field(default_factory=dict)
    route_lane: Optional[str] = None
    performance: Dict[str, Any] = Field(default_factory=dict)


class BasicStockSnapshot(BaseModel):
    """Fast stock snapshot that never calls an AI model."""

    stock_code: str
    stock_name: Optional[str] = None
    market: str
    quote: BasicQuotePayload
    profile: Optional[BasicProfilePayload] = None
    indicators: Dict[str, Any] = Field(default_factory=dict)
    trend: Optional[BasicTrendPayload] = None
    intelligence: Optional[BasicIntelligencePayload] = None
    route: Optional[BasicRoutePayload] = None
    warnings: List[BasicWarningPayload] = Field(default_factory=list)
    degradation: BasicDegradationPayload = Field(default_factory=BasicDegradationPayload)
    diagnostics: Optional[BasicQueryDiagnosticsPayload] = None
    ai_used: bool = False


class BasicPrewarmRequest(BaseModel):
    """Local quick-query cache prewarm request."""

    symbols: List[str] = Field(default_factory=list, max_length=20)


class BasicPrewarmResponse(BaseModel):
    """Local quick-query cache prewarm summary."""

    requested: int = 0
    warmed: int = 0
    degraded: int = 0
    symbols: List[str] = Field(default_factory=list)
    results: Dict[str, Any] = Field(default_factory=dict)
    elapsed_ms: float = Field(0, ge=0)
    ai_used: bool = False


class BasicMarketSourceItem(BaseModel):
    """One deterministic market data source in priority order."""

    source: str
    priority_rank: int = Field(..., ge=1)
    status: str = "ok"
    consecutive_failures: int = Field(0, ge=0)
    last_error: Optional[str] = None
    last_latency_ms: Optional[int] = None
    cooldown_remaining_sec: int = Field(0, ge=0)


class BasicMarketSourceLane(BaseModel):
    """Quick-query route lane and its ordered data source lists."""

    market: str
    channel: str
    route_lane: str
    quote_sources: List[BasicMarketSourceItem] = Field(default_factory=list)
    history_sources: List[BasicMarketSourceItem] = Field(default_factory=list)


class BasicMarketSourceOpsResponse(BaseModel):
    """Read-only local operations snapshot for market source health."""

    mode: str = "local_only"
    ai_used: bool = False
    generated_at: Optional[str] = None
    cache: Dict[str, Any] = Field(default_factory=dict)
    summary: Dict[str, Any] = Field(default_factory=dict)
    lanes: List[BasicMarketSourceLane] = Field(default_factory=list)


class BasicMarketSourceRecoveryRequest(BaseModel):
    """Admin-only local market source recovery request."""

    market: Optional[str] = None
    sources: List[str] = Field(default_factory=list, max_length=50)
    symbols: List[str] = Field(default_factory=list, max_length=20)
    prewarm: bool = True


class BasicMarketSourceRecoveryResponse(BaseModel):
    """Admin-only local market source recovery summary."""

    mode: str = "local_only"
    action: str = "reset_source_health"
    market: str = "all"
    reset_sources: List[str] = Field(default_factory=list)
    reset_count: int = Field(0, ge=0)
    prewarm: BasicPrewarmResponse = Field(default_factory=BasicPrewarmResponse)
    health: BasicMarketSourceOpsResponse
    ai_used: bool = False

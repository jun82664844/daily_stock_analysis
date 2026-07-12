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


class BasicReferenceQuotePayload(BaseModel):
    """One lightweight quote for a free peer or market reference."""

    stock_name: Optional[str] = None
    current_price: Optional[float] = None
    price: Optional[float] = None
    change: Optional[float] = None
    change_percent: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None
    update_time: Optional[str] = None
    freshness: str = Field("unavailable", pattern="^(fresh|cached|stale|unavailable)$")
    source: str = "reference_quote"
    status: str = Field("unavailable", pattern="^(available|unavailable)$")
    error: Optional[str] = None


class BasicComparisonTargetPayload(BaseModel):
    """One deterministic reference target for low-cost comparison context."""

    label: str
    symbol: str
    reason: str
    status: str = "reference_only"
    source: str = "no_ai_route_rules"
    reference_quote: Optional[BasicReferenceQuotePayload] = None


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
    reference_quote: Optional[BasicReferenceQuotePayload] = None


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


class BasicNewsCenterItemPayload(BaseModel):
    """One no-AI information lane shown in the local news center."""

    category: str
    title: str
    summary: str
    status: str = Field("degraded", pattern="^(available|degraded|unavailable)$")
    source: str = "no_ai_news_center_rules"
    action: str
    updated_at: Optional[str] = None
    url: Optional[str] = None


class BasicNewsCenterPayload(BaseModel):
    """Deterministic local information center for free no-AI users."""

    title: str
    summary: str
    items: List[BasicNewsCenterItemPayload] = Field(default_factory=list)
    source: str = "no_ai_news_center_rules"
    ai_used: bool = False
    public_search_used: bool = False
    premium_unlock: str
    boundary: str = "Information analysis only; not investment advice."


class BasicKlineForecastScenarioPayload(BaseModel):
    """One deterministic scenario in the K-line forecast lab preview."""

    label: str
    direction: str
    probability: int = Field(..., ge=0, le=100)
    trigger: str
    detail: str


class BasicKlineForecastPayload(BaseModel):
    """Kronos-ready local K-line forecast preview without model inference."""

    title: str
    horizon: str = "next_5_bars"
    direction: str
    confidence: int = Field(..., ge=0, le=100)
    support: Optional[float] = None
    resistance: Optional[float] = None
    scenarios: List[BasicKlineForecastScenarioPayload] = Field(default_factory=list)
    adapter_status: str
    source: str = "local_kline_rules_kronos_ready"
    ai_used: bool = False
    kronos_model_used: bool = False
    premium_unlock: str
    boundary: str = "Experimental model preview; information analysis only; not investment advice."


class BasicAShareReaderFactPayload(BaseModel):
    """One investor-readable fact for the A-share enrichment summary."""

    label: str
    value: str
    detail: str


class BasicAShareEnrichmentChannelPayload(BaseModel):
    """One local A-share enrichment channel inspired by a-stock-data."""

    category: str
    title: str
    summary: str
    status: str = Field("degraded", pattern="^(available|degraded|unavailable)$")
    source: str = "a_stock_data_poc_adapter"
    action: str
    details: List[BasicAShareReaderFactPayload] = Field(default_factory=list)
    updated_at: Optional[str] = None


class BasicAShareReaderMissPayload(BaseModel):
    """One missing or degraded A-share enrichment note."""

    title: str
    explanation: str
    next_step: str


class BasicAShareReaderSummaryPayload(BaseModel):
    """Reader-oriented A-share enrichment summary preserved through the API."""

    headline: str
    why_read: str
    key_facts: List[BasicAShareReaderFactPayload] = Field(default_factory=list)
    miss_explanations: List[BasicAShareReaderMissPayload] = Field(default_factory=list)
    premium_features: List[str] = Field(default_factory=list)
    boundary: str = "仅作信息分析，不构成投资建议。"


class BasicAShareEnrichmentPayload(BaseModel):
    """Local A-share enrichment payload that never invokes AI or public search."""

    title: str = "A-share enrichment"
    summary: str
    status: str = Field("degraded", pattern="^(available|degraded|unavailable)$")
    source: str = "a_stock_data_poc_adapter"
    source_mode: str = "poc"
    skill: Dict[str, Any] = Field(default_factory=dict)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    updated_at: Optional[str] = None
    ai_used: bool = False
    public_search_used: bool = False
    channels: List[BasicAShareEnrichmentChannelPayload] = Field(default_factory=list)
    reader_summary: Optional[BasicAShareReaderSummaryPayload] = None
    premium_unlock: str
    boundary: str = "Information analysis only; not investment advice."


class BasicGlobalEquityItemPayload(BaseModel):
    """One linked public-source fact for a US or Hong Kong equity."""

    title: Optional[str] = None
    summary: Optional[str] = None
    publisher: Optional[str] = None
    published_at: Optional[str] = None
    url: Optional[str] = None
    source: Optional[str] = None
    document_type: Optional[str] = None
    label: Optional[str] = None
    value: Optional[Any] = None


class BasicGlobalEquityChannelPayload(BaseModel):
    """One independent public data channel for US or Hong Kong equities."""

    category: str
    title: str
    summary: str
    status: str = Field("degraded", pattern="^(available|degraded|unavailable)$")
    source: str
    items: List[BasicGlobalEquityItemPayload] = Field(default_factory=list)
    official_url: Optional[str] = None
    action: str


class BasicGlobalEquityEnrichmentPayload(BaseModel):
    """No-AI direct public data expansion for US and Hong Kong equities."""

    title: str
    summary: str
    market: str = Field(..., pattern="^(us|hk)$")
    status: str = Field("degraded", pattern="^(available|degraded|unavailable)$")
    source: str = "global_equity_public_adapter"
    updated_at: Optional[str] = None
    ai_used: bool = False
    public_search_used: bool = False
    channels: List[BasicGlobalEquityChannelPayload] = Field(default_factory=list)
    diagnostics: Dict[str, Any] = Field(default_factory=dict)
    premium_unlock: str
    boundary: str = "Information and data only; not investment advice or a trading instruction."


class KronosForecastScenarioPayload(BaseModel):
    """One scenario returned by the local Kronos sandbox endpoint."""

    label: str
    direction: str
    probability: int = Field(..., ge=0, le=100)
    trigger: str
    detail: str


class KronosForecastPointPayload(BaseModel):
    """One predicted or fallback future K-line point."""

    timestamp: str
    open: Optional[float] = None
    high: Optional[float] = None
    low: Optional[float] = None
    close: Optional[float] = None
    volume: Optional[float] = None
    amount: Optional[float] = None


class KronosBacktestSummaryPayload(BaseModel):
    """Lightweight local record evaluation summary."""

    records: int = Field(0, ge=0)
    evaluated: int = Field(0, ge=0)
    hits: int = Field(0, ge=0)
    hit_rate: Optional[float] = None
    last_evaluated_at: Optional[str] = None


class KronosRuntimeMetricsPayload(BaseModel):
    """Secret-free evidence from one local Kronos runtime request."""

    resolved_device: str = "not_run"
    model_cache_hit: bool = False
    model_load_ms: float = Field(0, ge=0)
    inference_ms: float = Field(0, ge=0)
    peak_vram_mb: float = Field(0, ge=0)
    input_bars: int = Field(0, ge=0)
    forecast_bars: int = Field(0, ge=0)


class KronosForecastResponse(BaseModel):
    """Local Kronos forecast sandbox response with explicit fallback status."""

    stock_code: str
    stock_name: Optional[str] = None
    market: str
    mode: str = "kronos_sandbox"
    status: str = Field(..., pattern="^(model_ready|model_unavailable|model_disabled|model_error|premium_required)$")
    provider: str = "kronos"
    source: str
    horizon: str = "next_5_bars"
    lookback: int = Field(..., ge=5, le=512)
    direction: str
    confidence: int = Field(..., ge=0, le=100)
    support: Optional[float] = None
    resistance: Optional[float] = None
    adapter_status: str
    enabled: bool = False
    kronos_model_used: bool = False
    model_id: str
    tokenizer_id: str
    device: str
    dependency_status: Dict[str, bool] = Field(default_factory=dict)
    missing_dependencies: List[str] = Field(default_factory=list)
    runtime_metrics: KronosRuntimeMetricsPayload = Field(default_factory=KronosRuntimeMetricsPayload)
    scenarios: List[KronosForecastScenarioPayload] = Field(default_factory=list)
    forecast_points: List[KronosForecastPointPayload] = Field(default_factory=list)
    backtest_summary: KronosBacktestSummaryPayload = Field(default_factory=KronosBacktestSummaryPayload)
    warnings: List[str] = Field(default_factory=list)
    elapsed_ms: float = Field(..., ge=0)
    cache_hit: bool = False
    record_id: str
    ai_used: bool = False
    public_search_used: bool = False
    boundary: str = "Experimental model preview; information analysis only; not investment advice."


class BasicIntelligencePayload(BaseModel):
    """Low-cost information summary that never invokes AI or public search."""

    mode: str = "no_ai_low_cost"
    ai_used: bool = False
    market_brief: Optional[BasicMarketBriefPayload] = None
    free_insights: List[BasicFreeInsightPayload] = Field(default_factory=list)
    peer_comparison: Optional[BasicPeerComparisonPayload] = None
    signal_score: Optional[BasicSignalScorePayload] = None
    retention_brief: Optional[BasicRetentionBriefPayload] = None
    news_center: Optional[BasicNewsCenterPayload] = None
    kline_forecast: Optional[BasicKlineForecastPayload] = None
    a_share_enrichment: Optional[BasicAShareEnrichmentPayload] = None
    global_equity_enrichment: Optional[BasicGlobalEquityEnrichmentPayload] = None
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


class FinancialResearchFactPayload(BaseModel):
    """One observed fact used by a deterministic research workflow."""

    code: str
    label_zh: str
    label_en: str
    value: Any
    detail: Optional[str] = None
    unit: str
    currency: Optional[str] = None
    source: str
    freshness: str
    as_of: Optional[str] = None


class FinancialResearchWorkflowPayload(BaseModel):
    """One allowlisted information-only research workflow."""

    id: str
    title_zh: str
    title_en: str
    purpose_zh: str
    purpose_en: str
    status: str = Field(..., pattern="^(available|partial)$")
    source_reference: str
    facts: List[FinancialResearchFactPayload] = Field(default_factory=list)
    missing_data: List[str] = Field(default_factory=list)
    ai_used: bool = False
    public_search_used: bool = False


class FinancialResearchSourceWorkflowPayload(BaseModel):
    """Availability of one allowlisted workflow in the external source tree."""

    id: str
    source_reference: str
    available: bool = False


class FinancialResearchSourcePayload(BaseModel):
    """Read-only diagnostics for the installed workflow reference repository."""

    installed: bool = False
    source_name: str
    source_root_name: str
    license: str
    commit: Optional[str] = None
    accepted_commit: str
    commit_verified: bool = False
    external_code_executed: bool = False
    connectors_enabled: bool = False
    workflows: List[FinancialResearchSourceWorkflowPayload] = Field(default_factory=list)


class FinancialResearchWorkflowResponse(BaseModel):
    """No-AI research workflow response backed by the existing stock snapshot."""

    stock_code: str
    stock_name: Optional[str] = None
    market: str
    generated_at: Optional[str] = None
    mode: str = "deterministic_no_ai"
    ai_used: bool = False
    public_search_used: bool = False
    source: FinancialResearchSourcePayload
    workflows: List[FinancialResearchWorkflowPayload] = Field(default_factory=list)
    boundary_zh: str
    boundary_en: str


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

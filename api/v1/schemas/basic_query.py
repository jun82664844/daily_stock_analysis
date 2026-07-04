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


class BasicRoutePayload(BaseModel):
    """Resolved deterministic data lane for a no-AI query."""

    input_code: Optional[str] = None
    normalized_code: str
    market: str
    channel: str
    data_source_lane: str
    quote_sources: List[str] = Field(default_factory=list)
    history_sources: List[str] = Field(default_factory=list)
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


class BasicQueryDiagnosticsPayload(BaseModel):
    """Timing, cache, and source diagnostics for the no-AI query lane."""

    elapsed_ms: float = Field(..., ge=0)
    quote_elapsed_ms: float = Field(..., ge=0)
    history_elapsed_ms: float = Field(..., ge=0)
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
    indicators: Dict[str, Any] = Field(default_factory=dict)
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

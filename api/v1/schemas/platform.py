# -*- coding: utf-8 -*-
"""Pydantic models for public platform accounts."""

from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class PlatformRegisterRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=8, max_length=256)
    verification_code: Optional[str] = Field(default=None, alias="verificationCode", max_length=16)


class PlatformRegistrationVerificationRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)


class PlatformRegistrationVerificationResponse(BaseModel):
    email: str
    sent: bool
    expires_in_seconds: int
    dev_code: Optional[str] = None
    message: str


class PlatformLoginRequest(BaseModel):
    email: str = Field(..., min_length=3, max_length=255)
    password: str = Field(..., min_length=1, max_length=256)


class PlatformUserResponse(BaseModel):
    id: int
    email: str
    role: str
    plan: str
    status: str


class PlatformQuotaResponse(BaseModel):
    user_id: int
    plan: str
    weekly_limit: Optional[int]
    used: int
    remaining: Optional[int]
    period_start: str


class PlatformAuthResponse(BaseModel):
    user: PlatformUserResponse
    quota: PlatformQuotaResponse


class PlatformApiKeyUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    provider: str = Field(..., min_length=2, max_length=32)
    api_key: str = Field(..., alias="apiKey", min_length=8, max_length=4096)
    model: Optional[str] = Field(default=None, max_length=128)


class PlatformApiKeyItem(BaseModel):
    id: Optional[int] = None
    provider: str
    model: Optional[str] = None
    masked_key: str
    enabled: bool
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlatformStatusResponse(BaseModel):
    platform_auth_enabled: bool


class PlatformPlanUpdateRequest(BaseModel):
    plan: str = Field(..., min_length=2, max_length=32)


class PlatformWatchlistUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    stock_code: str = Field(..., alias="stockCode", min_length=1, max_length=64)


class PlatformWatchlistItem(BaseModel):
    id: Optional[int] = None
    stock_code: str
    input_code: Optional[str] = None
    market: str
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlatformWatchlistResponse(BaseModel):
    user_id: int
    items: List[PlatformWatchlistItem] = Field(default_factory=list)
    total: int = 0
    ai_used: bool = False


class PlatformWatchlistRefreshItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    market: str
    route_lane: Optional[str] = None
    current_price: Optional[float] = None
    change_percent: Optional[float] = None
    ma5: Optional[float] = None
    ma20: Optional[float] = None
    price_change_5d: Optional[float] = None
    price_change_20d: Optional[float] = None
    volume_change_percent: Optional[float] = None
    volume_signal: Optional[str] = None
    signal_score: Optional[int] = None
    updated_at: Optional[str] = None
    freshness: str
    degradation_status: str
    warning_codes: List[str] = Field(default_factory=list)
    ai_used: bool = False
    status: str


class PlatformWatchlistRefreshResponse(BaseModel):
    user_id: int
    requested: int = 0
    refreshed: int = 0
    degraded: int = 0
    items: List[PlatformWatchlistRefreshItem] = Field(default_factory=list)
    ai_used: bool = False


class PlatformWatchlistRadarEvent(BaseModel):
    stock_code: str
    type: str
    severity: str
    direction: str
    value: Optional[float] = None
    reference_value: Optional[float] = None
    title: Optional[str] = None
    summary: Optional[str] = None
    source_name: Optional[str] = None
    source_url: Optional[str] = None
    occurred_at: Optional[str] = None
    warning_codes: List[str] = Field(default_factory=list)
    ai_used: bool = False


class PlatformWatchlistRadarAlertSuggestion(BaseModel):
    stock_code: str
    type: str
    threshold: Optional[float] = None
    reference_value: Optional[float] = None
    ai_used: bool = False


class PlatformWatchlistRadarItem(PlatformWatchlistRefreshItem):
    events: List[PlatformWatchlistRadarEvent] = Field(default_factory=list)
    suggested_alerts: List[PlatformWatchlistRadarAlertSuggestion] = Field(default_factory=list)
    source_status: str


class PlatformWatchlistRadarSummaryItem(BaseModel):
    stock_code: str
    stock_name: Optional[str] = None
    change_percent: Optional[float] = None


class PlatformWatchlistRadarSummary(BaseModel):
    strongest: Optional[PlatformWatchlistRadarSummaryItem] = None
    weakest: Optional[PlatformWatchlistRadarSummaryItem] = None
    event_count: int = 0
    risk_count: int = 0
    source_event_count: int = 0


class PlatformWatchlistRadarResponse(BaseModel):
    user_id: int
    plan: str
    visible_limit: int
    total_watchlist: int
    processed: int
    hidden_count: int
    degraded: int
    summary: PlatformWatchlistRadarSummary
    items: List[PlatformWatchlistRadarItem] = Field(default_factory=list)
    events: List[PlatformWatchlistRadarEvent] = Field(default_factory=list)
    generated_at: str
    ai_used: bool = False
    analysis_boundary: str


class PlatformWatchlistAlertRuleUpsertRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    stock_code: str = Field(..., alias="stockCode", min_length=1, max_length=64)
    rule_type: str = Field(..., alias="ruleType", min_length=3, max_length=32)
    threshold: Optional[float] = Field(default=None, allow_inf_nan=False)
    reference_value: Optional[float] = Field(default=None, alias="referenceValue", allow_inf_nan=False)
    enabled: bool = True


class PlatformWatchlistAlertRuleItem(BaseModel):
    id: int
    stock_code: str
    rule_type: str
    threshold: Optional[float] = None
    reference_value: Optional[float] = None
    enabled: bool = True
    created_at: Optional[str] = None
    updated_at: Optional[str] = None


class PlatformWatchlistAlertRulesResponse(BaseModel):
    user_id: int
    plan: str
    limit: int
    total: int
    remaining: int
    items: List[PlatformWatchlistAlertRuleItem] = Field(default_factory=list)
    ai_used: bool = False


class PlatformWatchlistTriggeredAlert(BaseModel):
    rule_id: int
    stock_code: str
    rule_type: str
    direction: Optional[str] = None
    value: Optional[float] = None
    threshold: Optional[float] = None
    reference_value: Optional[float] = None
    ai_used: bool = False


class PlatformWatchlistRadarRunResponse(PlatformWatchlistRadarResponse):
    run_id: int
    triggered_alerts: List[PlatformWatchlistTriggeredAlert] = Field(default_factory=list)


class PlatformWatchlistRadarHistoryItem(BaseModel):
    id: int
    plan: str
    processed: int
    event_count: int
    risk_count: int
    source_event_count: int
    triggered_count: int
    strongest: Optional[PlatformWatchlistRadarSummaryItem] = None
    weakest: Optional[PlatformWatchlistRadarSummaryItem] = None
    created_at: Optional[str] = None


class PlatformWatchlistRadarHistoryResponse(BaseModel):
    user_id: int
    items: List[PlatformWatchlistRadarHistoryItem] = Field(default_factory=list)
    total: int
    ai_used: bool = False


class PlatformSnapshotHistorySaveRequest(BaseModel):
    snapshot: Dict[str, Any] = Field(default_factory=dict)
    note: Optional[str] = Field(default=None, max_length=512)


class PlatformSnapshotHistorySaveResponse(BaseModel):
    record_id: int
    stock_code: str
    stock_name: Optional[str] = None
    report_type: str = "basic_snapshot"
    saved_to_history: bool = True
    ai_used: bool = False


PlatformRetentionEventName = Literal[
    "free_query_completed",
    "registration_completed",
    "api_trial_submitted",
    "trial_report_opened",
    "premium_options_viewed",
]
PlatformRetentionEventSource = Literal["home", "registration", "trial", "report", "account"]


class PlatformRetentionEventRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="forbid")

    event: PlatformRetentionEventName
    session_id: str = Field(..., alias="sessionId", min_length=12, max_length=128, pattern=r"^[A-Za-z0-9._:-]+$")
    source: PlatformRetentionEventSource


class PlatformRetentionEventResponse(BaseModel):
    event: PlatformRetentionEventName
    accepted: bool
    duplicate: bool
    ai_used: bool = False

# -*- coding: utf-8 -*-
"""Pydantic models for public platform accounts."""

from __future__ import annotations

from typing import Any, Dict, List, Optional

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

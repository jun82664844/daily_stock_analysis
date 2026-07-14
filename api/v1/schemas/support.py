# -*- coding: utf-8 -*-
"""Request and response contracts for the DSA support center."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field, field_validator


SupportCategory = Literal[
    "account",
    "market_data",
    "model",
    "report",
    "alerts",
    "subscription",
    "bug",
    "other",
]
SupportStatus = Literal["open", "in_progress", "closed"]


def _strip_support_text(value: object) -> object:
    return value.strip() if isinstance(value, str) else value


class SupportTicketCreateRequest(BaseModel):
    category: SupportCategory
    subject: str = Field(..., min_length=4, max_length=120)
    message: str = Field(..., min_length=2, max_length=4000)

    _strip_text = field_validator("subject", "message", mode="before")(_strip_support_text)


class SupportMessageCreateRequest(BaseModel):
    message: str = Field(..., min_length=2, max_length=4000)

    _strip_text = field_validator("message", mode="before")(_strip_support_text)


class SupportStatusUpdateRequest(BaseModel):
    status: SupportStatus


class SupportMessageResponse(BaseModel):
    id: int
    ticket_id: int
    author_role: Literal["user", "admin"]
    body: str
    created_at: str | None = None


class SupportTicketSummaryResponse(BaseModel):
    id: int
    user_id: int
    requester_email: str | None = None
    category: SupportCategory
    subject: str
    status: SupportStatus
    unread_by_user: bool
    unread_by_admin: bool
    message_count: int
    created_at: str | None = None
    updated_at: str | None = None
    closed_at: str | None = None


class SupportTicketDetailResponse(SupportTicketSummaryResponse):
    messages: list[SupportMessageResponse] = Field(default_factory=list)


class SupportTicketEnvelope(BaseModel):
    ticket: SupportTicketDetailResponse


class SupportTicketListResponse(BaseModel):
    tickets: list[SupportTicketSummaryResponse] = Field(default_factory=list)
    total: int

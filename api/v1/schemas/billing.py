# -*- coding: utf-8 -*-
"""Pydantic models for billing boundary endpoints."""

from __future__ import annotations

from pydantic import BaseModel, Field


class CheckoutRequest(BaseModel):
    plan: str = Field(..., min_length=2, max_length=32)


class CheckoutResponse(BaseModel):
    checkout_url: str
    provider_session_id: str

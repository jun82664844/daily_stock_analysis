# -*- coding: utf-8 -*-
"""Feature-level cost and quota policy for public platform users."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass(frozen=True)
class FeaturePolicy:
    feature: str
    quota_bucket: str
    requires_ai: bool
    cost_units: int
    server_abuse_units: int
    weekly_limit: Optional[int]


PAID_PLAN_LIMITS = {
    "ai_quick": 100,
    "ai_quick_user_key": 500,
    "ai_deep": 30,
    "ai_deep_user_key": 500,
    "ai_local": 500,
    "market_review": 30,
}

PLAN_LIMITS = {
    "free": {
        "ai_quick": 5,
        "ai_quick_user_key": 25,
        "ai_deep": 0,
        "ai_deep_user_key": 50,
        "ai_local": 50,
        "market_review": 0,
    },
    "pro": PAID_PLAN_LIMITS,
    "premium": PAID_PLAN_LIMITS,
    "enterprise": {
        "ai_quick": None,
        "ai_quick_user_key": None,
        "ai_deep": None,
        "ai_deep_user_key": None,
        "ai_local": None,
        "market_review": None,
    },
}


def _limits_for_plan(plan: str) -> dict[str, Optional[int]]:
    normalized_plan = (plan or "free").strip().lower()
    return PLAN_LIMITS.get(normalized_plan, PLAN_LIMITS["free"])


def get_bucket_weekly_limit(quota_bucket: str, *, plan: str) -> Optional[int]:
    bucket = (quota_bucket or "").strip().lower()
    if bucket == "basic_query":
        return None
    if bucket == "analysis":
        return _limits_for_plan(plan)["ai_quick"]
    return _limits_for_plan(plan).get(bucket, 0)


def get_feature_policy(feature: str, *, plan: str, api_key_mode: str = "platform") -> FeaturePolicy:
    normalized_feature = (feature or "").strip().lower()
    normalized_mode = (api_key_mode or "platform").strip().lower()
    limits = _limits_for_plan(plan)

    if normalized_feature == "basic_query":
        return FeaturePolicy("basic_query", "basic_query", False, 0, 0, None)

    if normalized_feature in {"analysis", "ai_quick"} and normalized_mode == "user":
        return FeaturePolicy("ai_quick", "ai_quick_user_key", True, 0, 1, limits["ai_quick_user_key"])

    if normalized_feature in {"analysis", "ai_quick"} and normalized_mode == "local":
        return FeaturePolicy("ai_quick", "ai_local", True, 0, 1, limits["ai_local"])

    if normalized_feature in {"analysis", "ai_quick"}:
        return FeaturePolicy("ai_quick", "ai_quick", True, 1, 1, limits["ai_quick"])

    if normalized_feature == "ai_deep" and normalized_mode == "user":
        return FeaturePolicy("ai_deep", "ai_deep_user_key", True, 0, 1, limits["ai_deep_user_key"])

    if normalized_feature == "ai_deep" and normalized_mode == "local":
        return FeaturePolicy("ai_deep", "ai_local", True, 0, 1, limits["ai_local"])

    if normalized_feature == "ai_deep":
        return FeaturePolicy("ai_deep", "ai_deep", True, 3, 3, limits["ai_deep"])

    if normalized_feature == "market_review":
        return FeaturePolicy("market_review", "market_review", True, 2, 2, limits["market_review"])

    raise ValueError(f"Unsupported platform feature: {feature}")

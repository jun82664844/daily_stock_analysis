# -*- coding: utf-8 -*-
"""Request-scoped, owner-checked BYOK routing used by V111/V112."""

from __future__ import annotations

import copy
from dataclasses import dataclass, field
from typing import Any, Iterable, Optional

from src.platform_accounts import PlatformAccountService
from src.storage import DatabaseManager


class ByokRoutingError(ValueError):
    def __init__(self, code: str, message: str = "BYOK selection is unavailable") -> None:
        self.code = code
        super().__init__(f"{code}: {message}")


@dataclass(frozen=True)
class ByokSelection:
    api_key_id: int
    user_id: int
    provider: str
    model: str
    secret: str = field(repr=False)


class ByokRoutingService:
    APPROVED_PROVIDERS = {"deepseek", "openai", "anthropic"}

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.accounts = PlatformAccountService(self.db)

    def resolve_selection(
        self,
        *,
        user_id: int,
        api_key_id: int,
        provider: str,
        model: str,
        allowed_models: Iterable[str],
    ) -> ByokSelection:
        normalized_provider = (provider or "").strip().lower()
        normalized_model = (model or "").strip()
        if normalized_provider not in self.APPROVED_PROVIDERS:
            raise ByokRoutingError("byok_provider_not_allowed")
        if "/" not in normalized_model or normalized_model.split("/", 1)[0].lower() != normalized_provider:
            raise ByokRoutingError("byok_provider_mismatch")
        allowed = {(item or "").strip().lower() for item in allowed_models if (item or "").strip()}
        if normalized_model.lower() not in allowed:
            raise ByokRoutingError("byok_model_not_allowed")
        record = self.accounts.get_api_key_record(user_id, api_key_id)
        if record is None:
            raise ByokRoutingError("byok_key_not_found")
        if not record["enabled"]:
            raise ByokRoutingError("byok_key_disabled")
        if record["provider"] != normalized_provider:
            raise ByokRoutingError("byok_provider_mismatch")
        if (record.get("model") or "") != normalized_model:
            raise ByokRoutingError("byok_model_mismatch")
        secret = self.accounts.get_api_key_secret(user_id, normalized_provider)
        if not secret:
            raise ByokRoutingError("byok_key_unavailable")
        return ByokSelection(
            api_key_id=int(api_key_id),
            user_id=int(user_id),
            provider=normalized_provider,
            model=normalized_model,
            secret=secret,
        )

    @staticmethod
    def build_scoped_config(base_config: Any, selection: ByokSelection) -> Any:
        scoped = copy.copy(base_config)
        for name, value in (
            ("litellm_model", selection.model),
            ("agent_litellm_model", selection.model),
            ("litellm_fallback_models", []),
            ("litellm_config_path", None),
            ("llm_channels", []),
            ("llm_channel_names", []),
            ("llm_model_list", []),
            ("openai_base_url", None),
        ):
            setattr(scoped, name, value)
        for provider in ("deepseek", "openai", "anthropic", "gemini"):
            setattr(scoped, f"{provider}_api_key", None)
            setattr(scoped, f"{provider}_api_keys", [])
        setattr(scoped, f"{selection.provider}_api_key", selection.secret)
        setattr(scoped, f"{selection.provider}_api_keys", [selection.secret])
        return scoped

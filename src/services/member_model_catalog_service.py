# -*- coding: utf-8 -*-
"""Server-owned model option catalog for the simple V112 picker."""

from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from typing import Any, List, Optional

from src.platform_accounts import PlatformAccountService, normalize_membership_plan
from src.services.byok_routing_service import ByokRoutingError, ByokRoutingService
from src.services.user_local_connector_service import UserLocalConnectorService
from src.storage import DatabaseManager


@dataclass(frozen=True)
class MemberModelOption:
    option_id: str
    label_zh: str
    label_en: str
    source: str
    provider_label: str
    speed: str
    purpose: str
    quota_type: Optional[str]
    cost_units: int
    recommended: bool
    purpose_zh: str = ""
    purpose_en: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class ModelOptionNotAvailable(ValueError):
    pass


class MemberModelCatalogService:
    PROVIDER_DEFAULTS = {
        "deepseek": "deepseek/deepseek-v4-flash",
        "openai": "openai/gpt-4.1-mini",
        "anthropic": "anthropic/claude-3-5-haiku-latest",
    }

    def __init__(self, db_manager: Optional[DatabaseManager] = None) -> None:
        self.db = db_manager or DatabaseManager.get_instance()
        self.accounts = PlatformAccountService(self.db)

    def list_options(self, *, plan: str, user_id: Optional[int] = None) -> List[MemberModelOption]:
        normalized_plan = normalize_membership_plan(plan)
        options = [
            MemberModelOption(
                "platform_recommended",
                "平台推荐",
                "Platform recommended",
                "platform",
                "DSA",
                "fast",
                "快速资讯分析",
                "flash",
                1,
                True,
                "快速资讯分析",
                "Fast information analysis",
            )
        ]
        if normalized_plan in {"pro", "max", "enterprise"}:
            options.append(
                MemberModelOption(
                    "platform_pro",
                    "平台增强",
                    "Platform Pro",
                    "platform",
                    "DSA",
                    "strong",
                    "深度资讯整理",
                    "pro",
                    3,
                    False,
                    "深度资讯整理",
                    "Expanded information research",
                )
            )
        if normalized_plan in {"max", "enterprise"}:
            options.append(
                MemberModelOption(
                    "platform_flagship",
                    "平台旗舰",
                    "Platform flagship",
                    "platform",
                    "DSA",
                    "strong",
                    "复杂资料归纳",
                    "pro",
                    5,
                    False,
                    "复杂资料归纳",
                    "Complex information synthesis",
                )
            )
        if user_id is None:
            return options

        for key in self.accounts.list_api_keys(user_id):
            if not key["enabled"] or key["provider"] not in self.PROVIDER_DEFAULTS:
                continue
            options.append(
                MemberModelOption(
                    f"byok:{key['id']}:recommended",
                    f"我的 {key['provider'].title()}",
                    f"My {key['provider'].title()}",
                    "byok",
                    key["provider"].title(),
                    "balanced",
                    "使用我的 API",
                    None,
                    0,
                    False,
                    "使用我的 API",
                    "Use my API",
                )
            )

        connector_enabled = os.getenv(
            "PLATFORM_USER_LOCAL_CONNECTOR_ENABLED", "false"
        ).strip().lower() in {"1", "true", "yes", "on"}
        if connector_enabled:
            for connector in UserLocalConnectorService(self.db).list_online_connectors(user_id):
                for model_index, _model_name in enumerate(connector["models"]):
                    options.append(
                        MemberModelOption(
                            f"user_local:{connector['id']}:{model_index}",
                            f"本机模型 {model_index + 1}",
                            f"Local model {model_index + 1}",
                            "user_local",
                            "本机 Ollama",
                            "balanced",
                            "使用我的电脑运行",
                            None,
                            0,
                            False,
                            "使用我的电脑运行",
                            "Run on my computer",
                        )
                    )
        return options

    def _probe_provider(self, provider: str, api_key: str, model: str) -> bool:
        # Real provider verification is an explicit controlled acceptance gate.
        # Tests replace this boundary; local mode never sends secrets by default.
        raise ConnectionError("provider_unreachable")

    def connect_api_key(self, *, user_id: int, provider: str, api_key: str) -> dict[str, Any]:
        normalized_provider = (provider or "").strip().lower()
        if normalized_provider not in self.PROVIDER_DEFAULTS:
            raise ValueError("provider_not_supported")
        model = self.PROVIDER_DEFAULTS[normalized_provider]
        try:
            connected = self._probe_provider(normalized_provider, api_key, model)
        except PermissionError as exc:
            raise ValueError("invalid_api_key") from exc
        except ConnectionError as exc:
            raise ValueError("provider_unreachable") from exc
        if not connected:
            raise ValueError("invalid_api_key")
        item = self.accounts.store_api_key(
            user_id,
            provider=normalized_provider,
            api_key=api_key,
            model=model,
        )
        user = self.accounts.get_user(user_id)
        return {
            "api_key": item,
            "model_options": [option.to_dict() for option in self.list_options(plan=user.plan, user_id=user_id)],
        }

    def resolve(self, *, user_id: int, model_option_id: str) -> dict[str, Any]:
        option_id = (model_option_id or "platform_recommended").strip()
        user = self.accounts.get_user(user_id)
        if user is None:
            raise ModelOptionNotAvailable("model_option_not_available")
        options = {item.option_id: item for item in self.list_options(plan=user.plan, user_id=user_id)}
        option = options.get(option_id)
        if option is None:
            raise ModelOptionNotAvailable("model_option_not_available")
        if option.source == "platform":
            return {"option": option, "api_key_mode": "platform", "selection": None}
        if option.source == "user_local":
            try:
                _, connector_id_text, model_index_text = option_id.split(":", 2)
                connector_id = int(connector_id_text)
                model_index = int(model_index_text)
            except (ValueError, IndexError) as exc:
                raise ModelOptionNotAvailable("model_option_not_available") from exc
            connectors = {
                item["id"]: item
                for item in UserLocalConnectorService(self.db).list_online_connectors(user_id)
            }
            connector = connectors.get(connector_id)
            if connector is None or model_index < 0 or model_index >= len(connector["models"]):
                raise ModelOptionNotAvailable("model_option_not_available")
            return {
                "option": option,
                "api_key_mode": "user_local",
                "selection": {
                    "connector_id": connector_id,
                    "model_name": connector["models"][model_index],
                },
            }

        try:
            key_id = int(option_id.split(":", 2)[1])
        except (IndexError, ValueError) as exc:
            raise ModelOptionNotAvailable("model_option_not_available") from exc
        record = self.accounts.get_api_key_record(user_id, key_id)
        if record is None:
            raise ByokRoutingError("byok_key_not_found")
        model = record.get("model") or self.PROVIDER_DEFAULTS[record["provider"]]
        allowed = [
            item.strip()
            for item in os.getenv("PLATFORM_BYOK_ALLOWED_MODELS", "").split(",")
            if item.strip()
        ]
        selection = ByokRoutingService(self.db).resolve_selection(
            user_id=user_id,
            api_key_id=key_id,
            provider=record["provider"],
            model=model,
            allowed_models=allowed,
        )
        return {"option": option, "api_key_mode": "user", "selection": selection}

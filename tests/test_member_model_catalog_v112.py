# -*- coding: utf-8 -*-
from __future__ import annotations

import os
import tempfile
import unittest
from datetime import timedelta
from unittest.mock import patch

from src.platform_accounts import PlatformAccountService
from src.services.byok_routing_service import ByokRoutingError, ByokRoutingService
from src.services.member_model_catalog_service import MemberModelCatalogService, ModelOptionNotAvailable
from src.services.user_local_connector_service import UserLocalConnectorService
from src.storage import DatabaseManager, PlatformLocalConnector, utc_naive_now


class MemberModelCatalogV112TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "model-catalog-v112.sqlite")
        DatabaseManager.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.accounts = PlatformAccountService(self.db)
        self.catalog = MemberModelCatalogService(self.db)

    def tearDown(self) -> None:
        DatabaseManager.reset_instance()
        self.temp_dir.cleanup()

    @staticmethod
    def _ids(options):
        return [option.option_id for option in options]

    def test_catalog_filters_options_by_member_plan(self) -> None:
        self.assertEqual(self._ids(self.catalog.list_options(plan="free")), ["platform_recommended"])
        self.assertNotIn("platform_pro", self._ids(self.catalog.list_options(plan="plus")))
        self.assertIn("platform_pro", self._ids(self.catalog.list_options(plan="pro")))
        self.assertIn("platform_flagship", self._ids(self.catalog.list_options(plan="max")))

    def test_resolve_option_rechecks_key_ownership(self) -> None:
        user = self.accounts.create_user("catalog-owner@example.com", "password123", plan="pro")
        other = self.accounts.create_user("catalog-other@example.com", "password123", plan="pro")
        key = self.accounts.store_api_key(
            other.id,
            provider="deepseek",
            api_key="sk-other-secret",
            model="deepseek/deepseek-v4-flash",
        )
        with self.assertRaises(ModelOptionNotAvailable):
            self.catalog.resolve(
                user_id=user.id,
                model_option_id=f"byok:{key['id']}:recommended",
            )

    def test_byok_router_is_fail_closed_and_never_includes_secret_in_repr(self) -> None:
        user = self.accounts.create_user("router@example.com", "password123", plan="pro")
        key = self.accounts.store_api_key(
            user.id,
            provider="openai",
            api_key="sk-user-openai-secret",
            model="openai/gpt-4.1-mini",
        )
        router = ByokRoutingService(self.db)
        with self.assertRaisesRegex(ByokRoutingError, "byok_model_not_allowed"):
            router.resolve_selection(
                user_id=user.id,
                api_key_id=key["id"],
                provider="openai",
                model="openai/gpt-4.1-mini",
                allowed_models=[],
            )
        selection = router.resolve_selection(
            user_id=user.id,
            api_key_id=key["id"],
            provider="openai",
            model="openai/gpt-4.1-mini",
            allowed_models=["openai/gpt-4.1-mini"],
        )
        self.assertNotIn("sk-user-openai-secret", repr(selection))

    def test_online_user_connector_models_are_catalog_options_and_resolve_owner_only(self) -> None:
        user = self.accounts.create_user("local-catalog@example.com", "password123", plan="plus")
        connector_service = UserLocalConnectorService(self.db)
        pairing = connector_service.create_pairing(user_id=user.id)
        claimed = connector_service.claim_pairing(pairing["code"], device_name="Home PC")
        connector_service.heartbeat(claimed["device_token"], ["qwen3:8b", "deepseek-r1:14b"])

        with patch.dict(os.environ, {"PLATFORM_USER_LOCAL_CONNECTOR_ENABLED": "true"}, clear=False):
            options = self.catalog.list_options(plan="plus", user_id=user.id)
            local_options = [item for item in options if item.source == "user_local"]
            self.assertEqual(len(local_options), 2)
            resolved = self.catalog.resolve(
                user_id=user.id,
                model_option_id=local_options[0].option_id,
            )

        self.assertEqual(resolved["api_key_mode"], "user_local")
        self.assertEqual(resolved["selection"]["connector_id"], claimed["connector_id"])
        self.assertIn(resolved["selection"]["model_name"], {"qwen3:8b", "deepseek-r1:14b"})

    def test_stale_connector_is_not_offered_as_available_model(self) -> None:
        user = self.accounts.create_user("stale-local@example.com", "password123", plan="plus")
        connector_service = UserLocalConnectorService(self.db)
        pairing = connector_service.create_pairing(user_id=user.id)
        claimed = connector_service.claim_pairing(pairing["code"], device_name="Old PC")
        connector_service.heartbeat(claimed["device_token"], ["qwen3:8b"])
        with self.db.session_scope() as session:
            connector = session.get(PlatformLocalConnector, claimed["connector_id"])
            connector.last_seen_at = utc_naive_now() - timedelta(minutes=10)

        with patch.dict(
            os.environ,
            {
                "PLATFORM_USER_LOCAL_CONNECTOR_ENABLED": "true",
                "PLATFORM_LOCAL_CONNECTOR_ONLINE_TTL_SECONDS": "60",
            },
            clear=False,
        ):
            options = self.catalog.list_options(plan="plus", user_id=user.id)

        self.assertFalse(any(item.source == "user_local" for item in options))


if __name__ == "__main__":
    unittest.main()

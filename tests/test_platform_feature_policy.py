import os
import tempfile
import unittest
from unittest.mock import patch

from src.config import Config
from src.storage import DatabaseManager


class PlatformFeaturePolicyTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "feature-policy.sqlite")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(os.environ, {"DATABASE_PATH": self.db_path}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_basic_query_has_zero_ai_cost(self):
        from src.platform_feature_policy import get_feature_policy

        policy = get_feature_policy("basic_query", plan="free", api_key_mode="platform")

        self.assertEqual(policy.cost_units, 0)
        self.assertFalse(policy.requires_ai)
        self.assertEqual(policy.quota_bucket, "basic_query")

    def test_quick_ai_uses_free_weekly_bucket(self):
        from src.platform_feature_policy import get_feature_policy

        policy = get_feature_policy("ai_quick", plan="free", api_key_mode="platform")

        self.assertEqual(policy.cost_units, 1)
        self.assertTrue(policy.requires_ai)
        self.assertEqual(policy.quota_bucket, "ai_quick")
        self.assertEqual(policy.weekly_limit, 5)

    def test_user_owned_api_keeps_server_abuse_quota(self):
        from src.platform_feature_policy import get_feature_policy

        policy = get_feature_policy("ai_deep", plan="free", api_key_mode="user")

        self.assertEqual(policy.cost_units, 0)
        self.assertEqual(policy.server_abuse_units, 1)
        self.assertEqual(policy.quota_bucket, "ai_deep_user_key")

    def test_user_owned_quick_ai_uses_user_key_bucket(self):
        from src.platform_feature_policy import get_feature_policy

        policy = get_feature_policy("ai_quick", plan="free", api_key_mode="user")

        self.assertEqual(policy.cost_units, 0)
        self.assertEqual(policy.server_abuse_units, 1)
        self.assertEqual(policy.quota_bucket, "ai_quick_user_key")
        self.assertEqual(policy.weekly_limit, 25)

    def test_local_model_mode_uses_local_abuse_bucket(self):
        from src.platform_feature_policy import get_feature_policy

        policy = get_feature_policy("ai_deep", plan="pro", api_key_mode="local")

        self.assertEqual(policy.cost_units, 0)
        self.assertEqual(policy.server_abuse_units, 1)
        self.assertEqual(policy.quota_bucket, "ai_local")
        self.assertEqual(policy.weekly_limit, 500)

    def test_reserve_feature_quota_uses_distinct_buckets(self):
        from src.platform_accounts import PlatformAccountService

        service = PlatformAccountService()
        user = service.create_user("quota-buckets@example.com", "password123")

        service.reserve_feature_quota(user.id, "ai_quick")
        service.reserve_feature_quota(user.id, "ai_quick", api_key_mode="user")
        service.reserve_feature_quota(user.id, "ai_deep", api_key_mode="user")
        service.reserve_feature_quota(user.id, "ai_deep", api_key_mode="local")

        quick = service.get_feature_quota_status(user.id, "ai_quick")
        quick_user_key = service.get_feature_quota_status(user.id, "ai_quick_user_key")
        deep_platform = service.get_feature_quota_status(user.id, "ai_deep")
        deep_user_key = service.get_feature_quota_status(user.id, "ai_deep_user_key")
        local_model = service.get_feature_quota_status(user.id, "ai_local")

        self.assertEqual(quick["used"], 1)
        self.assertEqual(quick_user_key["used"], 1)
        self.assertEqual(deep_platform["used"], 0)
        self.assertEqual(deep_user_key["used"], 1)
        self.assertEqual(local_model["used"], 1)

import os
import tempfile
import unittest
from unittest.mock import Mock, patch
from types import SimpleNamespace

_TEST_ENVIRONMENT = os.environ.copy()

from api.v1.endpoints.analysis import _handle_async_analysis_batch
from src.config import Config
from src.platform_accounts import PlatformAccountService, QuotaExceeded
from src.platform_feature_policy import get_feature_policy
from src.services.task_queue import DuplicateTaskError
from src.storage import DatabaseManager
from src.services.stock_service import StockService


class PlatformFreeRetentionV93Tests(unittest.TestCase):
    def setUp(self):
        self._environment_before = _TEST_ENVIRONMENT.copy()
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "platform-free-retention.sqlite")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.db = DatabaseManager(db_url=f"sqlite:///{self.db_path}")
        self.accounts = PlatformAccountService(self.db)

    def tearDown(self):
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()
        for key in list(os.environ):
            if key not in self._environment_before:
                os.environ.pop(key, None)
        os.environ.update(self._environment_before)

    def test_free_and_pro_platform_api_quota_boundaries_are_explicit(self):
        free_quick = get_feature_policy("ai_quick", plan="free", api_key_mode="platform")
        free_deep = get_feature_policy("ai_deep", plan="free", api_key_mode="platform")
        pro_platform = get_feature_policy("ai_quick", plan="pro", api_key_mode="platform")
        pro_byok = get_feature_policy("ai_quick", plan="pro", api_key_mode="user")

        self.assertEqual(free_quick.quota_bucket, "ai_quick")
        self.assertEqual(free_quick.weekly_limit, 5)
        self.assertEqual(free_deep.weekly_limit, 0)
        self.assertEqual(pro_platform.weekly_limit, 100)
        self.assertEqual(pro_byok.quota_bucket, "ai_quick_user_key")
        self.assertEqual(pro_byok.weekly_limit, 500)

    def test_free_platform_api_trial_is_separate_from_byok_and_stops_at_five(self):
        user = self.accounts.create_user("free-trial@example.com", "password123")

        for _ in range(5):
            self.accounts.reserve_feature_quota(user.id, "ai_quick", api_key_mode="platform")
        platform_status = self.accounts.get_feature_quota_status(user.id, "ai_quick")
        self.assertEqual(platform_status["used"], 5)
        self.assertEqual(platform_status["remaining"], 0)

        with self.assertRaises(QuotaExceeded):
            self.accounts.reserve_feature_quota(user.id, "ai_quick", api_key_mode="platform")

        self.accounts.reserve_feature_quota(user.id, "ai_quick", api_key_mode="user")
        byok_status = self.accounts.get_feature_quota_status(user.id, "ai_quick_user_key")
        self.assertEqual(byok_status["used"], 1)
        self.assertEqual(byok_status["remaining"], 24)

    def test_unaccepted_async_reservation_can_be_released_by_reference(self):
        user = self.accounts.create_user("release-trial@example.com", "password123")

        self.accounts.reserve_feature_quota(
            user.id,
            "ai_quick",
            reference_id="analysis:reservation-1",
        )
        before_release = self.accounts.get_feature_quota_status(user.id, "ai_quick")
        self.assertEqual(before_release["used"], 1)

        self.accounts.release_feature_quota(
            user.id,
            "ai_quick",
            reference_id="analysis:reservation-1",
        )
        after_release = self.accounts.get_feature_quota_status(user.id, "ai_quick")
        self.assertEqual(after_release["used"], 0)
        self.assertEqual(after_release["remaining"], 5)

    def test_async_analysis_reserves_before_queue_and_releases_duplicates(self):
        request = SimpleNamespace(
            stock_name=None,
            original_query="AAPL",
            selection_source="manual",
            report_type="brief",
            analysis_phase="auto",
            analysis_depth="fast",
            force_refresh=False,
            notify=True,
            skills=None,
            report_language=None,
        )
        events = []
        queue = Mock()
        queue.submit_tasks_batch.side_effect = lambda **_: (
            events.append("queue"),
            ([], [DuplicateTaskError("AAPL", "existing-task")]),
        )[1]

        with patch("api.v1.endpoints.analysis._reserve_platform_analysis_quota", side_effect=lambda *args, **kwargs: events.append("reserve")), \
             patch("api.v1.endpoints.analysis._release_platform_analysis_quota", side_effect=lambda *args, **kwargs: events.append("release")), \
             patch("api.v1.endpoints.analysis.get_task_queue", return_value=queue):
            response = _handle_async_analysis_batch(["AAPL"], request, http_request=None)

        self.assertEqual(response.status_code, 409)
        self.assertEqual(events, ["reserve", "queue", "release"])

    def test_us_history_uses_yahoo_chart_when_primary_history_is_empty(self):
        service = StockService()
        manager = Mock()
        manager.get_daily_data.return_value = (None, "empty_primary")
        yahoo_result = {
            "meta": {"shortName": "Apple Inc."},
            "timestamp": [1783501200, 1783587600],
            "indicators": {
                "quote": [{
                    "open": [210.0, 212.0],
                    "high": [214.0, 215.0],
                    "low": [208.0, 211.0],
                    "close": [213.0, 214.5],
                    "volume": [50_000_000, 48_000_000],
                }],
            },
        }

        with patch("data_provider.base.DataFetcherManager", return_value=manager), patch.object(
            service,
            "_load_public_yahoo_chart",
            return_value=yahoo_result,
        ) as yahoo_loader:
            result = service.get_history_data("AAPL", period="daily", days=30)

        self.assertEqual(result["source"], "yahoo_chart_history")
        self.assertEqual(result["stock_name"], "Apple Inc.")
        self.assertEqual([row["close"] for row in result["data"]], [213.0, 214.5])
        yahoo_loader.assert_called_once()

    def test_a_share_history_does_not_use_us_hk_yahoo_fallback(self):
        service = StockService()
        manager = Mock()
        manager.get_daily_data.return_value = (None, "empty_primary")

        with patch("data_provider.base.DataFetcherManager", return_value=manager), patch.object(
            service,
            "_load_public_yahoo_chart",
            return_value={},
        ) as yahoo_loader:
            result = service.get_history_data("600519.SH", period="daily", days=30)

        self.assertEqual(result["data"], [])
        yahoo_loader.assert_not_called()

    def test_non_us_hk_suffixes_do_not_use_public_history_fallback(self):
        service = StockService()
        manager = Mock()
        manager.get_daily_data.return_value = (None, "empty_primary")

        with patch("data_provider.base.DataFetcherManager", return_value=manager), patch.object(
            service,
            "_load_public_yahoo_chart",
            return_value={},
        ) as yahoo_loader:
            for symbol in ("600519.SS", "SH600519", "SZ000001", "7203.T", "005930.KS"):
                with self.subTest(symbol=symbol):
                    result = service.get_history_data(symbol, period="daily", days=30)
                    self.assertEqual(result["data"], [])

        yahoo_loader.assert_not_called()

    def test_malformed_yahoo_history_degrades_to_empty_data(self):
        service = StockService()
        manager = Mock()
        manager.get_daily_data.return_value = (None, "empty_primary")
        malformed = {
            "meta": {"shortName": "Apple Inc."},
            "timestamp": ["not-a-timestamp"],
            "indicators": {"quote": [{"close": [214.5]}]},
        }

        with patch("data_provider.base.DataFetcherManager", return_value=manager), patch.object(
            service,
            "_load_public_yahoo_chart",
            return_value=malformed,
        ):
            result = service.get_history_data("AAPL", period="daily", days=30)

        self.assertEqual(result["data"], [])

    def test_dictionary_shaped_yahoo_quote_does_not_raise(self):
        service = StockService()
        manager = Mock()
        manager.get_daily_data.return_value = (None, "empty_primary")
        malformed = {
            "meta": {"shortName": "Apple Inc."},
            "timestamp": [1783501200],
            "indicators": {"quote": {"close": {"bad": 214.5}}},
        }

        with patch("data_provider.base.DataFetcherManager", return_value=manager), patch.object(
            service,
            "_load_public_yahoo_chart",
            return_value=malformed,
        ):
            result = service.get_history_data("AAPL", period="daily", days=30)

        self.assertEqual(result["data"], [])


if __name__ == "__main__":
    unittest.main()

# -*- coding: utf-8 -*-
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.platform_rate_limit import reset_platform_rate_limits
from src.storage import DatabaseManager


class BasicSnapshotRateLimitTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        root = Path(self.temp_dir.name)
        static_dir = root / "static"
        static_dir.mkdir()
        (static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        reset_platform_rate_limits()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(root / "rate-limit.sqlite"),
                "PLATFORM_RATE_LIMIT_ENABLED": "true",
                "PLATFORM_RATE_LIMIT_BASIC_SNAPSHOT_MAX": "1",
                "PLATFORM_RATE_LIMIT_WINDOW_SECONDS": "37",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        reset_platform_rate_limits()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_public_snapshot_returns_retry_countdown_when_rate_limited(self) -> None:
        snapshot = {
            "stock_code": "AAPL",
            "stock_name": "Apple Inc.",
            "market": "us",
            "quote": {
                "current_price": 200.0,
                "change_percent": 1.2,
                "source": "unit-test",
                "freshness": "fresh",
            },
            "indicators": {"ma5": 199.0, "ma20": 195.0},
        }
        with patch("src.services.basic_query_service.BasicQueryService.get_snapshot", return_value=snapshot):
            first = self.client.get("/api/v1/stocks/AAPL/snapshot")
            second = self.client.get("/api/v1/stocks/AAPL/snapshot")

        self.assertEqual(first.status_code, 200)
        self.assertEqual(second.status_code, 429)
        body = second.json()
        self.assertEqual(body["error"], "rate_limited")
        self.assertGreaterEqual(body["retry_after_seconds"], 1)
        self.assertLessEqual(body["retry_after_seconds"], 37)


if __name__ == "__main__":
    unittest.main()

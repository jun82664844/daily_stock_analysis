import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


class PlatformOllamaStatusApiV107TestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": str(Path(self.temp_dir.name) / "ollama-status.sqlite"),
                "PLATFORM_USER_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_status_is_public_and_contains_no_connection_details(self) -> None:
        status = {
            "enabled": True,
            "reachable": True,
            "ready": True,
            "quick_ready": True,
            "deep_ready": True,
            "reason": "ready",
            "runtime": "ollama",
            "quick_model": "quick-model",
            "deep_model": "deep-model",
            "quick_model_available": True,
            "deep_model_available": True,
            "max_concurrent": 1,
        }
        with patch(
            "src.services.ollama_runtime_service.OllamaRuntimeService.get_status",
            return_value=status,
        ):
            response = self.client.get("/api/v1/platform/local-model/status")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), status)
        self.assertNotIn("url", response.text.lower())
        self.assertNotIn("key", response.text.lower())


if __name__ == "__main__":
    unittest.main()

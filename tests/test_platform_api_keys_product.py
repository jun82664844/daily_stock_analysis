import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient

from api.app import create_app
from src.config import Config
from src.storage import DatabaseManager


class PlatformApiKeysProductTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "api-keys-product.sqlite")
        self.static_dir = Path(self.temp_dir.name) / "static"
        self.static_dir.mkdir()
        (self.static_dir / "index.html").write_text("<html>ok</html>", encoding="utf-8")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(
            os.environ,
            {
                "DATABASE_PATH": self.db_path,
                "PLATFORM_USER_AUTH_ENABLED": "true",
            },
            clear=False,
        )
        self.env_patch.start()
        self.client = TestClient(create_app(static_dir=self.static_dir))
        self.client.post(
            "/api/v1/platform/register",
            json={"email": "key-product@example.com", "password": "password123"},
        )

    def tearDown(self) -> None:
        self.client.close()
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_user_api_key_response_exposes_provider_model_and_mask_only(self):
        response = self.client.post(
            "/api/v1/platform/api-keys",
            json={
                "provider": "deepseek",
                "apiKey": "sk-secret-123456",
                "model": "deepseek/deepseek-v4-flash",
            },
        )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["provider"], "deepseek")
        self.assertEqual(body["model"], "deepseek/deepseek-v4-flash")
        self.assertTrue(body["masked_key"].startswith("sk-"))
        self.assertNotIn("secret-123456", str(body))

    def test_list_api_keys_keeps_model_metadata_without_plaintext(self):
        self.client.post(
            "/api/v1/platform/api-keys",
            json={
                "provider": "deepseek",
                "apiKey": "sk-secret-abcdef",
                "model": "deepseek/deepseek-v4-flash",
            },
        )

        response = self.client.get("/api/v1/platform/api-keys")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body[0]["model"], "deepseek/deepseek-v4-flash")
        self.assertNotIn("secret-abcdef", str(body))

    def test_model_options_hide_internal_model_names_and_base_urls(self):
        response = self.client.get("/api/v1/platform/model-options")

        self.assertEqual(response.status_code, 200)
        text = str(response.json()).lower()
        self.assertNotIn("base_url", text)
        self.assertNotIn("deepseek-v4", text)
        self.assertEqual(response.json()["selected_option_id"], "platform_recommended")

    def test_connect_api_key_returns_mask_and_options_without_plaintext(self):
        with patch(
            "src.services.member_model_catalog_service.MemberModelCatalogService._probe_provider",
            return_value=True,
        ):
            response = self.client.post(
                "/api/v1/platform/api-keys/connect",
                json={"provider": "deepseek", "apiKey": "sk-test-connect-secret"},
            )

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertTrue(body["api_key"]["masked_key"])
        self.assertTrue(body["model_options"])
        self.assertNotIn("sk-test-connect-secret", str(body))

import os
import tempfile
import unittest
from unittest.mock import patch

from src.config import Config
from src.platform_audit import PlatformAuditLogger
from src.storage import DatabaseManager


class PlatformAuditTestCase(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory(ignore_cleanup_errors=True)
        self.db_path = os.path.join(self.temp_dir.name, "audit.sqlite")
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.env_patch = patch.dict(os.environ, {"DATABASE_PATH": self.db_path}, clear=False)
        self.env_patch.start()

    def tearDown(self):
        self.env_patch.stop()
        DatabaseManager.reset_instance()
        Config.reset_instance()
        self.temp_dir.cleanup()

    def test_audit_event_redacts_secret_fields(self):
        logger = PlatformAuditLogger()
        logger.record(
            user_id=1,
            action="api_key_saved",
            metadata={"api_key": "sk-secret", "provider": "deepseek"},
        )

        events = logger.list_events(user_id=1)

        self.assertEqual(events[0]["metadata"]["api_key"], "[REDACTED]")
        self.assertEqual(events[0]["metadata"]["provider"], "deepseek")

    def test_audit_event_redacts_nested_secret_fields_and_token_strings(self):
        logger = PlatformAuditLogger()
        logger.record(
            user_id=1,
            action="diagnostic_failed",
            metadata={
                "provider": "deepseek",
                "request": {
                    "apiKey": "sk-nested-secret-123456",
                    "headers": {"Authorization": "Bearer sk-bearer-secret-abcdef"},
                },
                "message": "provider rejected key sk-inline-secret-xyz789",
                "attempts": [{"secret": "sk-list-secret-123456"}],
            },
        )

        metadata = logger.list_events(user_id=1)[0]["metadata"]

        self.assertEqual(metadata["request"]["apiKey"], "[REDACTED]")
        self.assertEqual(metadata["request"]["headers"]["Authorization"], "[REDACTED]")
        self.assertEqual(metadata["attempts"][0]["secret"], "[REDACTED]")
        self.assertNotIn("sk-nested-secret-123456", str(metadata))
        self.assertNotIn("sk-bearer-secret-abcdef", str(metadata))
        self.assertNotIn("sk-inline-secret-xyz789", str(metadata))
        self.assertEqual(metadata["provider"], "deepseek")

    def test_audit_events_are_returned_newest_first(self):
        logger = PlatformAuditLogger()
        logger.record(user_id=1, action="first", metadata={})
        logger.record(user_id=1, action="second", metadata={})

        events = logger.list_events(user_id=1)

        self.assertEqual([event["action"] for event in events[:2]], ["second", "first"])

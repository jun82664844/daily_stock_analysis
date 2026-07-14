from pathlib import Path
import tempfile
import unittest


class PlatformSupportNotificationsV122VerifierTestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_support_notifications_v122.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_SUPPORT_NOTIFICATIONS_V122_OK", text)
        self.assertIn("user_badge=true", text)
        self.assertIn("admin_badge=true", text)
        self.assertIn("polling=visible_only", text)
        self.assertIn("summary_redacted=true", text)
        self.assertIn("ai_reply=false", text)
        self.assertIn("external_notifications=false", text)

    def test_static_checks_fail_when_required_files_are_missing(self) -> None:
        from scripts.verify_platform_support_notifications_v122 import run_v122_checks

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_v122_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(any(item.status == "failed" for item in results))

    def test_current_contract_passes_static_checks(self) -> None:
        from scripts.verify_platform_support_notifications_v122 import run_v122_checks

        results = run_v122_checks(project_root=Path.cwd(), run_subprocess=False)
        self.assertTrue(all(item.status == "passed" for item in results), results)


if __name__ == "__main__":
    unittest.main()

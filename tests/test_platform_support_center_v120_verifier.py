from pathlib import Path
import tempfile
import unittest


class PlatformSupportCenterV120VerifierTestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_support_center_v120.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_SUPPORT_CENTER_V120_OK", text)
        self.assertIn("user_loop=true", text)
        self.assertIn("admin_queue=true", text)
        self.assertIn("ownership_isolated=true", text)
        self.assertIn("ai_reply=false", text)
        self.assertIn("attachments=false", text)
        self.assertIn("investment_advice=false", text)

    def test_static_checks_fail_when_required_files_are_missing(self) -> None:
        from scripts.verify_platform_support_center_v120 import run_v120_checks

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_v120_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(any(item.status == "failed" for item in results))

    def test_current_contract_passes_static_checks(self) -> None:
        from scripts.verify_platform_support_center_v120 import run_v120_checks

        results = run_v120_checks(project_root=Path.cwd(), run_subprocess=False)
        self.assertTrue(all(item.status == "passed" for item in results), results)


if __name__ == "__main__":
    unittest.main()

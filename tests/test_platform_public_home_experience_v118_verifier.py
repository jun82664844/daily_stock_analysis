from pathlib import Path
import tempfile
import unittest


class PlatformPublicHomeExperienceV118VerifierTestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_public_home_experience_v118.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_PUBLIC_HOME_EXPERIENCE_V118_OK", text)
        self.assertIn("markets=cn,hk,us", text)
        self.assertIn("public_news=true", text)
        self.assertIn("api_auto_run=false", text)
        self.assertIn("investment_advice=false", text)

    def test_static_checks_fail_when_required_files_are_missing(self) -> None:
        from scripts.verify_platform_public_home_experience_v118 import run_v118_checks

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_v118_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(any(item.status == "failed" for item in results))

    def test_contract_keeps_private_controls_out_of_default_home(self) -> None:
        from scripts.verify_platform_public_home_experience_v118 import run_v118_checks

        results = run_v118_checks(project_root=Path.cwd(), run_subprocess=False)
        self.assertTrue(all(item.status == "passed" for item in results), results)


if __name__ == "__main__":
    unittest.main()

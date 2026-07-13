from pathlib import Path
import tempfile
import unittest


class PlatformSixFeatureExperienceVerifierV117TestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_six_feature_experience_v117.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_SIX_FEATURE_EXPERIENCE_V117_OK", text)
        self.assertIn("features=6", text)
        self.assertIn("ollama=true", text)
        self.assertIn("investment_advice=false", text)

    def test_static_checks_fail_when_required_files_are_missing(self) -> None:
        from scripts.verify_platform_six_feature_experience_v117 import run_v117_checks

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_v117_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(any(item.status == "failed" for item in results))

    def test_verifier_names_the_six_product_capabilities(self) -> None:
        text = Path("scripts/verify_platform_six_feature_experience_v117.py").read_text(encoding="utf-8")
        for capability in (
            "kronos",
            "a_stock_data",
            "alphasift",
            "financial_services",
            "market_workspace",
            "market_pulse",
        ):
            self.assertIn(capability, text)


if __name__ == "__main__":
    unittest.main()

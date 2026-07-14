from pathlib import Path
import tempfile
import unittest


class PlatformFreeDailyMarketWorkbenchV124VerifierTestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_free_daily_market_workbench_v124.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_FREE_DAILY_MARKET_WORKBENCH_V124_OK", text)
        self.assertIn("guest=true", text)
        self.assertIn("public_data=true", text)
        self.assertIn("ai_used=false", text)
        self.assertIn("market_clocks=true", text)
        self.assertIn("cross_market_timeline=true", text)
        self.assertIn("recent_research=true", text)
        self.assertIn("bilingual=true", text)
        self.assertIn("investment_advice=false", text)

    def test_static_checks_fail_when_required_files_are_missing(self) -> None:
        from scripts.verify_platform_free_daily_market_workbench_v124 import run_v124_checks

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_v124_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(any(item.status == "failed" for item in results))

    def test_current_contract_passes_static_checks(self) -> None:
        from scripts.verify_platform_free_daily_market_workbench_v124 import run_v124_checks

        results = run_v124_checks(project_root=Path.cwd(), run_subprocess=False)
        self.assertTrue(all(item.status == "passed" for item in results), results)


if __name__ == "__main__":
    unittest.main()

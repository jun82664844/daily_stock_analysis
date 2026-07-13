from pathlib import Path
import tempfile
import unittest


class PlatformPublicMarketPriceAlertsVerifierV116TestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_public_market_price_alerts_v116.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_PUBLIC_MARKET_PRICE_ALERTS_V116_OK", text)
        self.assertIn("markets=cn,hk,us", text)
        self.assertIn("exact_price_alerts=true", text)
        self.assertIn("realtime_claim=false", text)

    def test_static_checks_fail_when_required_files_are_missing(self) -> None:
        from scripts.verify_platform_public_market_price_alerts_v116 import run_v116_checks

        with tempfile.TemporaryDirectory() as temp_dir:
            results = run_v116_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(any(item.status == "failed" for item in results))

    def test_verifier_scans_v116_copy_for_prohibited_claims(self) -> None:
        text = Path("scripts/verify_platform_public_market_price_alerts_v116.py").read_text(encoding="utf-8")
        self.assertIn("实时股价", text)
        self.assertIn("real-time price", text)
        self.assertIn("全市场热门推荐", text)


if __name__ == "__main__":
    unittest.main()

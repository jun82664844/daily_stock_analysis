from pathlib import Path
import unittest


class PlatformMarketWorkspaceVerifierV113TestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_market_workspace_v113.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_MARKET_WORKSPACE_V113_OK", text)
        self.assertIn("markets=cn,hk,us", text)
        self.assertIn("ai_required=false", text)
        self.assertIn("agpl_code_copied=false", text)

    def test_verifier_locks_api_prefix_timeout_and_market_reset_contracts(self) -> None:
        text = Path("scripts/verify_platform_market_workspace_v113.py").read_text(encoding="utf-8")
        self.assertIn("PLATFORM_MARKET_WORKSPACE_OVERVIEW_TIMEOUT_SECONDS", text)
        self.assertIn("/api/v1/market-workspace/overview", text)
        self.assertIn("key={overview.market}", text)


if __name__ == "__main__":
    unittest.main()

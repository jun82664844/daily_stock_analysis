from pathlib import Path
import unittest


class PlatformUnifiedMarketDataVerifierV115TestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_unified_market_data_v115.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_UNIFIED_MARKET_DATA_V115_OK", text)
        self.assertIn("canonical_snapshot=true", text)
        self.assertIn("source_arbitration=true", text)
        self.assertIn("no_averaging=true", text)
        self.assertIn("ai_required=false", text)

    def test_verifier_locks_contract_and_user_visible_diagnostics(self) -> None:
        text = Path("scripts/verify_platform_unified_market_data_v115.py").read_text(encoding="utf-8")
        self.assertIn("freshness_then_priority_then_observed_at", text)
        self.assertIn("deduplicate_snapshot_intelligence", text)
        self.assertIn("统一事实快照", text)


if __name__ == "__main__":
    unittest.main()

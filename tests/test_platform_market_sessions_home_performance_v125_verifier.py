from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class MarketSessionsHomePerformanceV125VerifierTestCase(unittest.TestCase):
    def test_latest_homepage_chunk_uses_mtime_and_enforces_500kb(self) -> None:
        from scripts.verify_platform_market_sessions_home_performance_v125 import (
            homepage_bundle_check,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            assets = Path(temp_dir)
            older = assets / "HomePage-old.js"
            newer = assets / "HomePage-new.js"
            older.write_bytes(b"x" * 510_000)
            newer.write_bytes(b"x" * 499_999)
            older.touch()
            newer.touch()
            older_mtime = newer.stat().st_mtime - 10
            older.touch()
            older.chmod(older.stat().st_mode)
            import os
            os.utime(older, (older_mtime, older_mtime))

            result = homepage_bundle_check(assets)

        self.assertTrue(result.ok)
        self.assertEqual(result.details["filename"], "HomePage-new.js")
        self.assertEqual(result.details["size_bytes"], 499_999)

    def test_lazy_contract_requires_query_only_components_to_be_dynamic(self) -> None:
        from scripts.verify_platform_market_sessions_home_performance_v125 import (
            lazy_component_contract,
        )

        source = """
const DecisionJourneyV91 = lazy(() => import('../components/analysis/DecisionJourneyV91'));
const FreeApiTrialPanelV93 = lazy(() => import('../components/retention/FreeApiTrialPanelV93'));
const WatchlistEventRadarV99 = lazy(() => import('../components/radar/WatchlistEventRadarV99'));
const DailyResearchCockpitV103 = lazy(() => import('../components/radar/DailyResearchCockpitV103'));
const GlobalEquityEnrichmentCard = lazy(() => import('../components/research/GlobalEquityEnrichmentCard'));
"""

        self.assertTrue(lazy_component_contract(source).ok)
        self.assertFalse(lazy_component_contract(source.replace("lazy(() => ", "")).ok)


if __name__ == "__main__":
    unittest.main()

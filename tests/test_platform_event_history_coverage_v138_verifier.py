from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatformEventHistoryCoverageV138VerifierTestCase(unittest.TestCase):
    def test_verifier_exists_and_static_contracts_pass(self) -> None:
        verifier = (
            REPO_ROOT
            / "scripts/verify_platform_event_history_coverage_v138.py"
        )
        self.assertTrue(verifier.is_file())

        from scripts.verify_platform_event_history_coverage_v138 import (
            run_static_checks,
        )

        checks = list(run_static_checks(REPO_ROOT))
        self.assertGreaterEqual(len(checks), 5)
        self.assertTrue(
            all(check.ok for check in checks),
            {check.name: check.details for check in checks if not check.ok},
        )

    def test_verifier_declares_focused_suites_and_marker(self) -> None:
        source = (
            REPO_ROOT
            / "scripts/verify_platform_event_history_coverage_v138.py"
        ).read_text(encoding="utf-8")

        for token in (
            "tests.test_public_event_history_coverage_v138",
            "tests.test_public_market_calendar_service_v135",
            "tests.test_public_market_event_reaction_service_v136",
            "MarketEventReactionPanelV136.test.tsx",
            "marketWorkspace.test.ts",
            "DSA_PLATFORM_EVENT_HISTORY_COVERAGE_V138_OK",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()

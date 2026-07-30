from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatformEventDataAvailabilityV137VerifierTestCase(unittest.TestCase):
    def test_verifier_exists_and_static_contracts_pass(self) -> None:
        verifier = (
            REPO_ROOT
            / "scripts/verify_platform_event_data_availability_v137.py"
        )
        self.assertTrue(verifier.is_file())

        from scripts.verify_platform_event_data_availability_v137 import (
            run_static_checks,
        )

        checks = list(run_static_checks(REPO_ROOT))
        self.assertGreaterEqual(len(checks), 5)
        self.assertTrue(
            all(check.ok for check in checks),
            {check.name: check.details for check in checks if not check.ok},
        )

    def test_verifier_declares_focused_backend_and_frontend_suites(self) -> None:
        source = (
            REPO_ROOT
            / "scripts/verify_platform_event_data_availability_v137.py"
        ).read_text(encoding="utf-8")

        for token in (
            "tests.test_public_event_reaction_cache_v137",
            "tests.test_public_event_reaction_availability_v137",
            "tests.test_public_event_reaction_startup_v137",
            "MarketEventReactionPanelV136.test.tsx",
            "marketWorkspace.test.ts",
            "DSA_PLATFORM_EVENT_DATA_AVAILABILITY_V137_OK",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()

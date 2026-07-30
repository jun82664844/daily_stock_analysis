from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatformSymbolEventArchiveV139VerifierTestCase(unittest.TestCase):
    def test_verifier_exists_and_static_contracts_pass(self) -> None:
        verifier = REPO_ROOT / "scripts/verify_platform_symbol_event_archive_v139.py"
        self.assertTrue(verifier.is_file())

        from scripts.verify_platform_symbol_event_archive_v139 import (
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
            REPO_ROOT / "scripts/verify_platform_symbol_event_archive_v139.py"
        ).read_text(encoding="utf-8")
        for token in (
            "tests.test_public_symbol_event_archive_v139",
            "tests.test_public_event_history_coverage_v138",
            "SymbolEventArchiveV139.test.tsx",
            "MarketWorkspacePage.test.tsx",
            "DSA_PLATFORM_SYMBOL_EVENT_ARCHIVE_V139_OK",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()

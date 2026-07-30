from __future__ import annotations

import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


class PlatformStockResearchOverviewV142VerifierTestCase(unittest.TestCase):
    def test_verifier_exists_and_static_contracts_pass(self) -> None:
        verifier = REPO_ROOT / "scripts/verify_platform_stock_research_overview_v142.py"
        self.assertTrue(verifier.is_file())

        from scripts.verify_platform_stock_research_overview_v142 import run_static_checks

        checks = list(run_static_checks(REPO_ROOT))
        self.assertGreaterEqual(len(checks), 6)
        self.assertTrue(
            all(check.ok for check in checks),
            {check.name: check.details for check in checks if not check.ok},
        )

    def test_verifier_declares_focused_suites_and_marker(self) -> None:
        source = (
            REPO_ROOT / "scripts/verify_platform_stock_research_overview_v142.py"
        ).read_text(encoding="utf-8")
        for token in (
            "tests.test_public_stock_research_overview_v142",
            "StockResearchOverviewV142.test.tsx",
            "src/api/__tests__/stocks.test.ts",
            "src/pages/__tests__/HomePage.test.tsx",
            "DSA_PLATFORM_STOCK_RESEARCH_OVERVIEW_V142_OK",
        ):
            self.assertIn(token, source)


if __name__ == "__main__":
    unittest.main()

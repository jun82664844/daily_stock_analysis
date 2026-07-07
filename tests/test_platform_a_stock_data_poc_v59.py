from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_a_stock_data_poc_v59 import REQUIRED_MARKERS, OK_MARKER, run_checks


class PlatformAStockDataPocV59VerifierTestCase(unittest.TestCase):
    def _write_minimal_tree(self, root: Path) -> None:
        for rel_path, markers in REQUIRED_MARKERS.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(markers) + "\n", encoding="utf-8")

    def test_verifier_passes_when_all_v59_markers_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_tree(root)

            results = run_checks(root)

            self.assertTrue(results)
            self.assertTrue(all(result.status == "passed" for result in results))
            self.assertIn(OK_MARKER, (root / "docs/superpowers/plans/2026-07-07-dsa-v59-a-stock-data-poc.md").read_text(encoding="utf-8"))

    def test_verifier_fails_when_frontend_panel_marker_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_tree(root)
            homepage = root / "apps/dsa-web/src/pages/HomePage.tsx"
            homepage.write_text(
                homepage.read_text(encoding="utf-8").replace('data-testid="basic-query-a-share-enrichment"', ""),
                encoding="utf-8",
            )

            results = run_checks(root)

            failed = [result for result in results if result.status == "failed"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0].check_id, "apps/dsa-web/src/pages/HomePage.tsx")
            self.assertIn('data-testid="basic-query-a-share-enrichment"', failed[0].missing)


if __name__ == "__main__":
    unittest.main()

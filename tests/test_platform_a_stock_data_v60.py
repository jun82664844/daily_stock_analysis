from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_a_stock_data_v60 import REQUIRED_MARKERS, OK_MARKER, run_checks


# Expected marker: DSA_PLATFORM_A_STOCK_DATA_V60_OK
class PlatformAStockDataV60VerifierTestCase(unittest.TestCase):
    def _write_minimal_tree(self, root: Path) -> None:
        for rel_path, markers in REQUIRED_MARKERS.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(markers) + "\n", encoding="utf-8")

    def test_verifier_passes_when_all_v60_markers_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_tree(root)

            results = run_checks(root)

            self.assertTrue(results)
            self.assertTrue(all(result.status == "passed" for result in results))
            plan_text = (root / "docs/superpowers/plans/2026-07-07-dsa-v60-a-stock-data-source.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(OK_MARKER, plan_text)

    def test_verifier_fails_when_cache_marker_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_tree(root)
            service_path = root / "src/services/a_share_enrichment_service.py"
            service_path.write_text(
                service_path.read_text(encoding="utf-8").replace("A_STOCK_DATA_CACHE_TTL_SEC", ""),
                encoding="utf-8",
            )

            results = run_checks(root)

            failed = [result for result in results if result.status == "failed"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0].check_id, "src/services/a_share_enrichment_service.py")
            self.assertIn("A_STOCK_DATA_CACHE_TTL_SEC", failed[0].missing)


if __name__ == "__main__":
    unittest.main()

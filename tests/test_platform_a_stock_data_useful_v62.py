from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_a_stock_data_useful_v62 import OK_MARKER, REQUIRED_MARKERS, run_checks


# Expected marker: DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK
class PlatformAStockDataUsefulV62VerifierTestCase(unittest.TestCase):
    def _write_minimal_tree(self, root: Path) -> None:
        for rel_path, markers in REQUIRED_MARKERS.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text("\n".join(markers) + "\n", encoding="utf-8")

    def test_verifier_passes_when_all_v62_markers_exist(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_tree(root)

            results = run_checks(root)

            self.assertTrue(results)
            self.assertTrue(all(result.status == "passed" for result in results))
            plan_text = (root / "docs/superpowers/plans/2026-07-07-dsa-v62-a-stock-data-useful.md").read_text(
                encoding="utf-8"
            )
            self.assertIn(OK_MARKER, plan_text)

    def test_verifier_fails_when_public_payload_marker_is_missing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            self._write_minimal_tree(root)
            service_path = root / "src/services/a_share_enrichment_service.py"
            service_path.write_text(
                service_path.read_text(encoding="utf-8").replace("_fetch_public_a_stock_payload", ""),
                encoding="utf-8",
            )

            results = run_checks(root)

            failed = [result for result in results if result.status == "failed"]
            self.assertEqual(len(failed), 1)
            self.assertEqual(failed[0].check_id, "src/services/a_share_enrichment_service.py")
            self.assertIn("_fetch_public_a_stock_payload", failed[0].missing)


if __name__ == "__main__":
    unittest.main()

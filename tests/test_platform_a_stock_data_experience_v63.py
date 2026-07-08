from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlatformAStockDataExperienceV63VerifierTestCase(unittest.TestCase):
    def _write_required_files(self, root: Path, *, service_text: str | None = None) -> None:
        from scripts.verify_platform_a_stock_data_experience_v63 import REQUIRED_MARKERS

        for rel_path, markers in REQUIRED_MARKERS.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            text = "\n".join(markers) + "\n"
            if rel_path == "src/services/a_share_enrichment_service.py" and service_text is not None:
                text = service_text
            path.write_text(text, encoding="utf-8")

    def test_verifier_passes_when_all_v63_markers_exist(self) -> None:
        from scripts.verify_platform_a_stock_data_experience_v63 import OK_MARKER, run_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_required_files(root)

            results = run_checks(root)

        self.assertTrue(results)
        self.assertTrue(all(result.status == "passed" for result in results))
        self.assertEqual(OK_MARKER, "DSA_PLATFORM_A_STOCK_DATA_EXPERIENCE_V63_OK")

    def test_verifier_fails_when_reader_summary_marker_is_missing(self) -> None:
        from scripts.verify_platform_a_stock_data_experience_v63 import run_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_required_files(root, service_text="def _reader_summary\n")

            results = run_checks(root)

        by_id = {result.check_id: result for result in results}
        service_result = by_id["src/services/a_share_enrichment_service.py"]
        self.assertEqual(service_result.status, "failed")
        self.assertIn('"reader_summary"', service_result.missing)


if __name__ == "__main__":
    unittest.main()

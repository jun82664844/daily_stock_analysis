from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from scripts.verify_platform_global_equity_public_data_v110 import MARKERS, REQUIRED_FILES, static_checks


class GlobalEquityPublicDataV110VerifierTests(unittest.TestCase):
    def test_static_check_passes_with_required_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            for index, relative in enumerate(REQUIRED_FILES):
                path = root / relative
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text("\n".join(MARKERS) if index == 0 else "v110", encoding="utf-8")
            (root / ".env.example").write_text("GLOBAL_EQUITY_ENRICHMENT_ENABLED=false", encoding="utf-8")
            result = static_checks(root)
        self.assertTrue(result["passed"])

    def test_static_check_reports_missing_files_and_markers(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            (root / ".env.example").write_text("", encoding="utf-8")
            result = static_checks(root)
        self.assertFalse(result["passed"])
        self.assertEqual(set(result["missing_files"]), set(REQUIRED_FILES))
        self.assertEqual(set(result["missing_markers"]), set(MARKERS))


if __name__ == "__main__":
    unittest.main()

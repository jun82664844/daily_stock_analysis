from __future__ import annotations

import tempfile
import unittest
from pathlib import Path


class PlatformFreeResearchBoardV67VerifierTestCase(unittest.TestCase):
    def _write_required_files(self, root: Path, *, home_page_text: str | None = None) -> None:
        from scripts.verify_platform_free_research_board_v67 import REQUIRED_MARKERS

        for rel_path, markers in REQUIRED_MARKERS.items():
            path = root / rel_path
            path.parent.mkdir(parents=True, exist_ok=True)
            text = "\n".join(markers) + "\n"
            if rel_path == "apps/dsa-web/src/pages/HomePage.tsx" and home_page_text is not None:
                text = home_page_text
            path.write_text(text, encoding="utf-8")

    def test_verifier_passes_when_all_v67_markers_exist(self) -> None:
        from scripts.verify_platform_free_research_board_v67 import OK_MARKER, run_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_required_files(root)

            results = run_checks(root)

        self.assertTrue(results)
        self.assertTrue(all(result.status == "passed" for result in results))
        self.assertEqual(OK_MARKER, "DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK")

    def test_verifier_fails_when_free_research_board_marker_is_missing(self) -> None:
        from scripts.verify_platform_free_research_board_v67 import run_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_required_files(root, home_page_text="basic-query-professional-overview\n")

            results = run_checks(root)

        by_id = {result.check_id: result for result in results}
        home_result = by_id["apps/dsa-web/src/pages/HomePage.tsx"]
        self.assertEqual(home_result.status, "failed")
        self.assertIn("basic-query-free-research-board", home_result.missing)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformFreeKlineResearchV101VerifierTestCase(unittest.TestCase):
    def test_v101_verifier_is_importable_and_has_stable_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_free_kline_research_v101.py"

        self.assertTrue(verifier.exists())
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_free_kline_research_v101"))
        from scripts.verify_platform_free_kline_research_v101 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_FREE_KLINE_RESEARCH_V101_OK")

    def test_required_file_check_reports_missing_files_without_subprocesses(self) -> None:
        from scripts.verify_platform_free_kline_research_v101 import run_v101_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_v101_checks(project_root=Path(temp_dir), run_subprocess=False)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v101_required_files"].status, "failed")
        self.assertGreater(len(by_id["v101_required_files"].metadata["missing_files"]), 0)


if __name__ == "__main__":
    unittest.main()

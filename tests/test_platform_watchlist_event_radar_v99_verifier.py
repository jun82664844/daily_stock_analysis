import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformWatchlistEventRadarV99VerifierTestCase(unittest.TestCase):
    def test_v99_verifier_is_importable_and_has_stable_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_watchlist_event_radar_v99.py"

        self.assertTrue(verifier.exists())
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_watchlist_event_radar_v99"))
        from scripts.verify_platform_watchlist_event_radar_v99 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_WATCHLIST_EVENT_RADAR_V99_OK")

    def test_required_file_check_reports_missing_files_without_running_subprocesses(self) -> None:
        from scripts.verify_platform_watchlist_event_radar_v99 import run_v99_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_v99_checks(project_root=Path(temp_dir), python_exe="python", run_subprocess=False)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v99_required_files"].status, "failed")
        self.assertGreater(len(by_id["v99_required_files"].metadata["missing_files"]), 0)


if __name__ == "__main__":
    unittest.main()

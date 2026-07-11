import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformAShareFreeQuerySpeedV102VerifierTestCase(unittest.TestCase):
    def test_v102_verifier_is_importable_and_has_stable_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_a_share_free_query_speed_v102.py"

        self.assertTrue(verifier.exists())
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_a_share_free_query_speed_v102"))
        from scripts.verify_platform_a_share_free_query_speed_v102 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_A_SHARE_FREE_QUERY_SPEED_V102_OK")

    def test_required_file_and_source_checks_fail_cleanly_without_subprocesses(self) -> None:
        from scripts.verify_platform_a_share_free_query_speed_v102 import run_v102_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_v102_checks(project_root=Path(temp_dir), run_subprocess=False)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["v102_required_files"].status, "failed")
        self.assertEqual(by_id["v102_source_contract"].status, "failed")


if __name__ == "__main__":
    unittest.main()

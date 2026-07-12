import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformOllamaLocalRetentionV107VerifierTestCase(unittest.TestCase):
    def test_verifier_is_visible_and_has_stable_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_ollama_local_retention_v107.py"
        self.assertTrue(verifier.exists())
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_ollama_local_retention_v107"))
        from scripts.verify_platform_ollama_local_retention_v107 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_OLLAMA_LOCAL_RETENTION_V107_OK")

    def test_static_checks_fail_cleanly_for_empty_project(self) -> None:
        from scripts.verify_platform_ollama_local_retention_v107 import run_v107_checks

        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_v107_checks(
                project_root=Path(temp_dir),
                run_subprocess=False,
                check_live_runtime=False,
            )
        self.assertTrue(results)
        self.assertTrue(all(result.status == "failed" for result in results))

    def test_local_submit_refreshes_account_quota_without_page_reload(self) -> None:
        root = Path(__file__).resolve().parents[1]
        source = (root / "apps" / "dsa-web" / "src" / "pages" / "HomePage.tsx").read_text(
            encoding="utf-8"
        )
        handler = source.split("const handleLocalModelQuickAnalyze", 1)[1].split(
            "const handlePlatformApiTrial", 1
        )[0]

        self.assertIn("useCallback(async", handler)
        self.assertIn("await submitAnalysis", handler)
        self.assertIn("await loadPlatformAccount(platformSession)", handler)


if __name__ == "__main__":
    unittest.main()

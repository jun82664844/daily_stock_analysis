import importlib.util
import tempfile
import unittest
from pathlib import Path


class PlatformFinancialResearchWorkflowsV106VerifierTestCase(unittest.TestCase):
    def test_verifier_is_visible_and_has_stable_marker(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_financial_research_workflows_v106.py"
        self.assertTrue(verifier.exists())
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_financial_research_workflows_v106"))
        from scripts.verify_platform_financial_research_workflows_v106 import OK_MARKER
        self.assertEqual(OK_MARKER, "DSA_PLATFORM_FINANCIAL_RESEARCH_WORKFLOWS_V106_OK")

    def test_static_checks_fail_cleanly_for_empty_project(self) -> None:
        from scripts.verify_platform_financial_research_workflows_v106 import run_v106_checks
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            results = run_v106_checks(project_root=Path(temp_dir), run_subprocess=False)
        self.assertTrue(all(result.status == "failed" for result in results))


if __name__ == "__main__":
    unittest.main()

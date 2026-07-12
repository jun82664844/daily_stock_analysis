from pathlib import Path
import unittest


class PlatformSimpleModelAccessVerifierV112TestCase(unittest.TestCase):
    def test_verifier_is_visible_and_contains_stable_marker(self) -> None:
        path = Path("scripts/verify_platform_simple_model_access_v112.py")
        self.assertTrue(path.exists())
        text = path.read_text(encoding="utf-8")
        self.assertIn("DSA_PLATFORM_SIMPLE_MODEL_ACCESS_V112_OK", text)
        self.assertIn("secrets_exposed=false", text)

    def test_verifier_isolates_non_csrf_product_tests_from_local_runtime_config(self) -> None:
        text = Path("scripts/verify_platform_simple_model_access_v112.py").read_text(encoding="utf-8")
        self.assertIn('"PLATFORM_CSRF_ENABLED": "false"', text)

    def test_billing_verifier_isolates_non_csrf_tests_from_local_runtime_config(self) -> None:
        text = Path("scripts/verify_platform_billing_lifecycle.py").read_text(encoding="utf-8")
        self.assertIn('"PLATFORM_CSRF_ENABLED": "false"', text)


if __name__ == "__main__":
    unittest.main()

import importlib.util
import re
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
ENV_TEMPLATE = REPO_ROOT / "docs" / "superpowers" / "platform-production-env.example"


REQUIRED_SAFE_VALUES = {
    "ADMIN_AUTH_ENABLED": "true",
    "PLATFORM_USER_AUTH_ENABLED": "true",
    "PLATFORM_CSRF_ENABLED": "true",
    "BILLING_ENABLED": "false",
    "BILLING_PROVIDER": "disabled",
    "SEARXNG_PUBLIC_INSTANCES_ENABLED": "false",
    "ENABLE_FUNDAMENTAL_PIPELINE": "false",
    "ENABLE_CHIP_DISTRIBUTION": "false",
    "DAILY_MARKET_CONTEXT_ENABLED": "false",
    "DEBUG": "false",
    "CORS_ALLOW_ALL": "false",
    "LOCAL_LLM_ENABLED": "false",
    "DSA_REAL_PAYMENT_APPROVED": "false",
    "DSA_PAYMENT_WEBHOOK_APPROVED": "false",
    "DSA_PRODUCTION_DOMAIN_APPROVED": "false",
    "DSA_PRODUCTION_HTTPS_APPROVED": "false",
    "DSA_PRODUCTION_WAF_APPROVED": "false",
    "DSA_MARKET_DATA_LICENSE_APPROVED": "false",
    "DSA_LEGAL_TERMS_APPROVED": "false",
    "DSA_PRIVACY_POLICY_APPROVED": "false",
    "DSA_MONITORING_APPROVED": "false",
    "DSA_BACKUP_RESTORE_DRILL_APPROVED": "false",
    "DSA_ANALYSIS_NOT_INVESTMENT_ADVICE": "true",
}

BLANK_SECRET_PLACEHOLDERS = {
    "BILLING_STRIPE_SECRET_KEY",
    "BILLING_STRIPE_WEBHOOK_SECRET",
    "BILLING_STRIPE_PRICE_PRO",
}

SECRET_PATTERNS = (
    re.compile(r"\bsk-[A-Za-z0-9._-]{8,}\b"),
    re.compile(r"\bwhsec_[A-Za-z0-9._-]{8,}\b"),
)


def _parse_env(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


class PlatformProductionEnvGatesV50TestCase(unittest.TestCase):
    def test_production_env_template_has_explicit_safe_approval_gates(self) -> None:
        values = _parse_env(ENV_TEMPLATE)

        missing = sorted(set(REQUIRED_SAFE_VALUES) - set(values))
        unsafe = {
            key: {"expected": expected, "actual": values.get(key)}
            for key, expected in REQUIRED_SAFE_VALUES.items()
            if values.get(key, "").lower() != expected
        }

        self.assertEqual(missing, [])
        self.assertEqual(unsafe, {})

    def test_real_provider_placeholders_are_blank_and_secret_free(self) -> None:
        values = _parse_env(ENV_TEMPLATE)

        for key in BLANK_SECRET_PLACEHOLDERS:
            self.assertIn(key, values)
            self.assertEqual(values[key], "")

        text = ENV_TEMPLATE.read_text(encoding="utf-8")
        leaked = [pattern.pattern for pattern in SECRET_PATTERNS if pattern.search(text)]
        self.assertEqual(leaked, [])

    def test_v50_verifier_file_and_marker_are_visible(self) -> None:
        verifier = REPO_ROOT / "scripts" / "verify_platform_production_env_gates_v50.py"

        self.assertTrue(verifier.exists(), "V50 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_production_env_gates_v50"))

        from scripts.verify_platform_production_env_gates_v50 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK")


if __name__ == "__main__":
    unittest.main()

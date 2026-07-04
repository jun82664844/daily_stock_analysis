# -*- coding: utf-8 -*-
import importlib.util
import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


class PlatformLocalMarketPrewarmConsoleV12TestCase(unittest.TestCase):
    def test_v12_verifier_file_and_marker_are_visible(self) -> None:
        root = Path(__file__).resolve().parents[1]
        verifier = root / "scripts" / "verify_platform_local_market_prewarm_console_v12.py"

        self.assertTrue(verifier.exists(), "V12 verifier script is missing")
        self.assertIsNotNone(importlib.util.find_spec("scripts.verify_platform_local_market_prewarm_console_v12"))

        from scripts.verify_platform_local_market_prewarm_console_v12 import OK_MARKER

        self.assertEqual(OK_MARKER, "DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK")

    def test_v12_evaluator_requires_no_ai_complete_prewarm_summary(self) -> None:
        from scripts.verify_platform_local_market_prewarm_console_v12 import evaluate_prewarm_console_payload

        valid = evaluate_prewarm_console_payload(
            {
                "requested": 4,
                "warmed": 3,
                "degraded": 1,
                "symbols": ["600519", "AAPL", "HK00700", "BTC-USD"],
                "results": {},
                "elapsed_ms": 42,
                "ai_used": False,
            }
        )
        missing = evaluate_prewarm_console_payload(
            {
                "requested": 4,
                "warmed": 4,
                "degraded": 0,
                "symbols": ["AAPL"],
                "results": {},
                "elapsed_ms": 42,
                "ai_used": True,
            }
        )

        self.assertEqual(valid, [])
        self.assertIn("ai_used_not_false", missing)
        self.assertIn("symbols_incomplete", missing)

    def test_v12_frontend_check_uses_resolved_npm_command(self) -> None:
        from scripts.verify_platform_local_market_prewarm_console_v12 import _run_frontend_admin_test_check

        completed = subprocess.CompletedProcess(args=["npm"], returncode=0, stdout="ok", stderr="")
        with patch("scripts.verify_platform_local_market_prewarm_console_v12._resolve_executable", return_value="C:/node/npm.cmd"), \
             patch("scripts.verify_platform_local_market_prewarm_console_v12.subprocess.run", return_value=completed) as run_command:
            result = _run_frontend_admin_test_check(Path("C:/repo"))

        self.assertEqual(result.status, "passed")
        self.assertEqual(run_command.call_args.args[0][0], "C:/node/npm.cmd")


if __name__ == "__main__":
    unittest.main()

from __future__ import annotations

import subprocess
import unittest
from pathlib import Path
from unittest.mock import patch


REPO_ROOT = Path(__file__).resolve().parents[1]


class FreeMarketCalendarV134VerifierTestCase(unittest.TestCase):
    def test_verifier_entrypoint_exists(self) -> None:
        self.assertTrue(
            (REPO_ROOT / "scripts/verify_platform_free_market_calendar_v134.py").is_file()
        )

    def test_frontend_contract_requires_honest_bilingual_calendar_boundaries(self) -> None:
        from scripts.verify_platform_free_market_calendar_v134 import frontend_contract

        valid = """
data-testid="market-event-calendar-v134"
免费市场日历
Free market calendar
计划日期
Scheduled date
发布时间
Published time
1/3/5/20-day follow-up checkpoints
事件与行情并列展示不代表因果关系。
Showing an event beside market observations does not establish causality.
日历仅整理公开资讯和本地检查点，不构成投资建议。
This calendar only organizes public information and local checkpoints. Not investment advice.
CALENDAR_PAST_DAYS = 7
CALENDAR_FUTURE_DAYS = 30
MAX_MARKET_CALENDAR_ENTRIES = 48
MAX_CALENDAR_ACKNOWLEDGEMENTS = 128
"""
        self.assertTrue(frontend_contract(valid).ok)
        self.assertFalse(frontend_contract(valid.replace("不构成投资建议", "建议立即买入")).ok)

    def test_privacy_cost_contract_rejects_network_ai_and_identity_leaks(self) -> None:
        from scripts.verify_platform_free_market_calendar_v134 import privacy_cost_contract

        valid = "localStorage.setItem(key, JSON.stringify(ids)); const scope = 'user-72';"
        self.assertTrue(privacy_cost_contract(valid).ok)
        self.assertFalse(privacy_cost_contract(valid + " fetch('/api/calendar')").ok)
        self.assertFalse(privacy_cost_contract(valid + " const provider = 'ollama';").ok)
        self.assertFalse(privacy_cost_contract(valid + " const identity = user.email;").ok)

    def test_time_basis_contract_requires_explicit_dates_windows_and_caps(self) -> None:
        from scripts.verify_platform_free_market_calendar_v134 import time_basis_contract

        valid = """
extractExplicitScheduleAt
dateBasis: explicitSchedule ? 'explicit_schedule' : 'published'
dateBasis: 'follow_up_checkpoint' as const
buildFollowUpCheckpoints(followed, now)
CALENDAR_PAST_DAYS * DAY_MILLISECONDS
CALENDAR_FUTURE_DAYS * DAY_MILLISECONDS
entries.slice(0, MAX_MARKET_CALENDAR_ENTRIES)
"""
        self.assertTrue(time_basis_contract(valid).ok)
        self.assertFalse(time_basis_contract(valid.replace("'published'", "'upcoming'")).ok)

    def test_scope_contract_requires_numeric_user_scope_and_home_wiring(self) -> None:
        from scripts.verify_platform_free_market_calendar_v134 import scope_wiring_contract

        helper = r"""
/^user-\d+$/
adoptGuestCalendarAcknowledgements
marketEventCalendarStorageKey('guest')
"""
        daily = """
<MarketEventCalendarPanelV134
scope={eventFollowUpScope}
"""
        home = (
            "eventFollowUpScope={platformSession ? "
            "`user-${platformSession.user.id}` : 'guest'}"
        )
        self.assertTrue(scope_wiring_contract(helper, daily, home).ok)
        self.assertFalse(scope_wiring_contract(helper, daily, home.replace("user.id", "user.email")).ok)

    def test_regression_contract_requires_domain_panel_and_integration_paths(self) -> None:
        from scripts.verify_platform_free_market_calendar_v134 import regression_tests_contract

        valid = """
extracts only explicit ISO, Chinese, or English schedule dates
builds three-market public entries and 1/3/5/20 day follow-up checkpoints
keeps only the seven-day history and thirty-day future window
matches personalized symbols exactly instead of using substrings or cross-exchange codes
tracks unseen due reminders and caps acknowledgement storage
moves guest acknowledgement state only into a numeric signed-in scope
renders an honest Chinese calendar with schedule, publication, and follow-up time bases
filters due reviews and acknowledges them locally
keeps followed checkpoints visible when the public event stream fills the display limit
adds and removes V134 follow-up calendar checkpoints with the V133 follow state
"""
        self.assertTrue(regression_tests_contract(valid).ok)
        self.assertFalse(regression_tests_contract(valid.replace("exactly", "loosely")).ok)

    def test_focused_vitest_check_uses_real_test_process_exit_code(self) -> None:
        from scripts.verify_platform_free_market_calendar_v134 import focused_vitest_check

        with (
            patch(
                "scripts.verify_platform_free_market_calendar_v134.shutil.which",
                return_value="npm.cmd",
            ),
            patch(
                "scripts.verify_platform_free_market_calendar_v134.subprocess.run",
            ) as run,
        ):
            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=0,
                stdout="Tests 99 passed",
                stderr="",
            )
            result = focused_vitest_check(REPO_ROOT)
            self.assertTrue(result.ok)
            command = " ".join(run.call_args.args[0])
            self.assertIn("marketEventCalendarV134.test.ts", command)
            self.assertIn("MarketEventCalendarPanelV134.test.tsx", command)
            self.assertIn("DailyMarketEventCenterV126.test.tsx", command)
            self.assertIn("HomePage.test.tsx", command)

            run.return_value = subprocess.CompletedProcess(
                args=[],
                returncode=1,
                stdout="Tests 1 failed",
                stderr="",
            )
            self.assertFalse(focused_vitest_check(REPO_ROOT).ok)


if __name__ == "__main__":
    unittest.main()

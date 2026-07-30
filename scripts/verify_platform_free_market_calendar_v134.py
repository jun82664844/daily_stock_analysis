from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_platform_event_driven_research_v132 import homepage_bundle_check


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: Dict[str, Any]


def frontend_contract(source: str) -> CheckResult:
    required = (
        'data-testid="market-event-calendar-v134"',
        "免费市场日历",
        "Free market calendar",
        "计划日期",
        "Scheduled date",
        "发布时间",
        "Published time",
        "1/3/5/20-day follow-up checkpoints",
        "事件与行情并列展示不代表因果关系。",
        "Showing an event beside market observations does not establish causality.",
        "日历仅整理公开资讯和本地检查点，不构成投资建议。",
        "This calendar only organizes public information and local checkpoints. Not investment advice.",
        "CALENDAR_PAST_DAYS = 7",
        "CALENDAR_FUTURE_DAYS = 30",
        "MAX_MARKET_CALENDAR_ENTRIES = 48",
        "MAX_CALENDAR_ACKNOWLEDGEMENTS = 128",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("v134_calendar_frontend", not missing, {"missing": missing})


def privacy_cost_contract(source: str) -> CheckResult:
    forbidden = (
        "fetch(",
        "axios",
        "openai",
        "litellm",
        "deepseek",
        "ollama",
        "sendemail",
        "sendsms",
        "pushnotification",
        "platform_user_id",
        ".email",
    )
    lowered = source.casefold()
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "v134_no_network_ai_or_identity_leak",
        not forbidden_hits,
        {"forbidden_hits": forbidden_hits},
    )


def time_basis_contract(helper_source: str) -> CheckResult:
    required = (
        "extractExplicitScheduleAt",
        "dateBasis: explicitSchedule ? 'explicit_schedule' : 'published'",
        "dateBasis: 'follow_up_checkpoint' as const",
        "buildFollowUpCheckpoints(followed, now)",
        "CALENDAR_PAST_DAYS * DAY_MILLISECONDS",
        "CALENDAR_FUTURE_DAYS * DAY_MILLISECONDS",
        "entries.slice(0, MAX_MARKET_CALENDAR_ENTRIES)",
    )
    missing = [token for token in required if token not in helper_source]
    return CheckResult("v134_honest_time_basis_and_caps", not missing, {"missing": missing})


def scope_wiring_contract(helper_source: str, daily_source: str, home_test_source: str) -> CheckResult:
    required = (
        r"/^user-\d+$/",
        "adoptGuestCalendarAcknowledgements",
        "marketEventCalendarStorageKey('guest')",
        "<MarketEventCalendarPanelV134",
        "scope={eventFollowUpScope}",
        "eventFollowUpScope={platformSession ? `user-${platformSession.user.id}` : 'guest'}",
    )
    combined = f"{helper_source}\n{daily_source}\n{home_test_source}"
    missing = [token for token in required if token not in combined]
    unsafe_identity = "user.email" in combined or "platform_user_id" in combined.casefold()
    return CheckResult(
        "v134_numeric_scope_and_home_wiring",
        not missing and not unsafe_identity,
        {"missing": missing, "unsafe_identity": unsafe_identity},
    )


def regression_tests_contract(source: str) -> CheckResult:
    required = (
        "extracts only explicit ISO, Chinese, or English schedule dates",
        "builds three-market public entries and 1/3/5/20 day follow-up checkpoints",
        "keeps only the seven-day history and thirty-day future window",
        "matches personalized symbols exactly instead of using substrings or cross-exchange codes",
        "tracks unseen due reminders and caps acknowledgement storage",
        "moves guest acknowledgement state only into a numeric signed-in scope",
        "renders an honest Chinese calendar with schedule, publication, and follow-up time bases",
        "filters due reviews and acknowledges them locally",
        "keeps followed checkpoints visible when the public event stream fills the display limit",
        "adds and removes V134 follow-up calendar checkpoints with the V133 follow state",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("v134_regression_test_contract", not missing, {"missing": missing})


def focused_vitest_check(repo_root: Path) -> CheckResult:
    npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_executable is None:
        return CheckResult("v134_focused_vitest", False, {"reason": "npm_not_found"})
    test_files = (
        "src/components/market-home/__tests__/marketEventCalendarV134.test.ts",
        "src/components/market-home/__tests__/MarketEventCalendarPanelV134.test.tsx",
        "src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
        "src/pages/__tests__/HomePage.test.tsx",
    )
    completed = subprocess.run(
        [npm_executable, "test", "--", "--run", *test_files],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    output_lines = [
        line.strip()
        for line in f"{completed.stdout}\n{completed.stderr}".splitlines()
        if line.strip()
    ]
    return CheckResult(
        "v134_focused_vitest",
        completed.returncode == 0,
        {
            "returncode": completed.returncode,
            "test_files": list(test_files),
            "summary": " | ".join(output_lines[-6:]),
        },
    )


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    helper_path = repo_root / "apps/dsa-web/src/components/market-home/marketEventCalendarV134.ts"
    panel_path = repo_root / "apps/dsa-web/src/components/market-home/MarketEventCalendarPanelV134.tsx"
    daily_path = repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx"
    market_home_path = repo_root / "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx"
    home_page_path = repo_root / "apps/dsa-web/src/pages/HomePage.tsx"
    helper_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/marketEventCalendarV134.test.ts"
    panel_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/MarketEventCalendarPanelV134.test.tsx"
    daily_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx"
    home_test_path = repo_root / "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx"

    helper_source = helper_path.read_text(encoding="utf-8")
    panel_source = panel_path.read_text(encoding="utf-8")
    daily_source = daily_path.read_text(encoding="utf-8")
    home_test_source = home_test_path.read_text(encoding="utf-8")
    tests_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (helper_test_path, panel_test_path, daily_test_path, home_test_path)
    )

    yield frontend_contract(f"{helper_source}\n{panel_source}")
    yield privacy_cost_contract(f"{helper_source}\n{panel_source}")
    yield time_basis_contract(helper_source)
    yield scope_wiring_contract(helper_source, daily_source, home_test_source)
    yield regression_tests_contract(tests_source)
    yield focused_vitest_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            helper_path,
            panel_path,
            daily_path,
            market_home_path,
            home_page_path,
            helper_test_path,
            panel_test_path,
            daily_test_path,
            home_test_path,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V134 free market calendar and local reminders."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_FREE_MARKET_CALENDAR_V134_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

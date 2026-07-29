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
        'data-testid="market-event-follow-up-panel-v133"',
        "事件后续追踪",
        "Event follow-up",
        "关注时基准",
        "Follow-time baseline",
        "后续公开事件",
        "Later public events",
        "不代表事件导致行情变化",
        "does not mean the event caused the market change",
        "仅提供公开资讯和数据，不构成投资建议。",
        "Public information and data only. Not investment advice.",
        "FOLLOW_UP_HORIZON_DAYS = [1, 3, 5, 20]",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("v133_follow_up_frontend", not missing, {"missing": missing})


def privacy_cost_contract(source: str) -> CheckResult:
    forbidden = (
        "fetch(",
        "axios",
        "openai",
        "litellm",
        "ollama",
        "platform_user_id",
        ".email",
    )
    lowered = source.casefold()
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "v133_no_network_ai_or_identity_leak",
        not forbidden_hits,
        {"forbidden_hits": forbidden_hits},
    )


def scope_contract(helper_source: str, home_page_source: str) -> CheckResult:
    helper_required = (
        r"/^user-\d+$/",
        "adoptGuestFollowedMarketEvents",
        "marketEventFollowUpStorageKey('guest')",
        "MAX_FOLLOWED_EVENTS = 12",
        "MAX_OBSERVATIONS = 32",
    )
    home_required = (
        "eventFollowUpScope={platformSession ? `user-${platformSession.user.id}` : 'guest'}",
    )
    missing = [
        token
        for token in (*helper_required, *home_required)
        if token not in f"{helper_source}\n{home_page_source}"
    ]
    unsafe_identity = (
        "eventFollowUpScope={platformSession ? `user-${platformSession.user.email}`"
        in home_page_source
    )
    return CheckResult(
        "v133_local_scope_and_caps",
        not missing and not unsafe_identity,
        {"missing": missing, "unsafe_identity": unsafe_identity},
    )


def regression_tests_contract(source: str) -> CheckResult:
    required = (
        "persists a followed event with an honest follow-time quote baseline",
        "moves current guest follows into the signed-in user scope without leaking to another user",
        "records exact-symbol public quote observations and replaces the same UTC day",
        "builds 1/3/5/20 day checkpoints without inventing missing observations",
        "shows a Chinese follow-up record with checkpoints and explicit information-only boundaries",
        "lets a guest follow and remove an event from the V132 research card",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("v133_regression_test_contract", not missing, {"missing": missing})


def focused_vitest_check(repo_root: Path) -> CheckResult:
    npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_executable is None:
        return CheckResult("v133_focused_vitest", False, {"reason": "npm_not_found"})
    test_files = (
        "src/components/market-home/__tests__/marketEventFollowUpV133.test.ts",
        "src/components/market-home/__tests__/MarketEventFollowUpPanelV133.test.tsx",
        "src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
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
        "v133_focused_vitest",
        completed.returncode == 0,
        {
            "returncode": completed.returncode,
            "test_files": list(test_files),
            "summary": " | ".join(output_lines[-6:]),
        },
    )


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    helper_path = repo_root / "apps/dsa-web/src/components/market-home/marketEventFollowUpV133.ts"
    panel_path = repo_root / "apps/dsa-web/src/components/market-home/MarketEventFollowUpPanelV133.tsx"
    research_path = repo_root / "apps/dsa-web/src/components/market-home/MarketEventResearchPanelV132.tsx"
    daily_path = repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx"
    market_home_path = repo_root / "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx"
    home_page_path = repo_root / "apps/dsa-web/src/pages/HomePage.tsx"
    helper_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/marketEventFollowUpV133.test.ts"
    panel_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/MarketEventFollowUpPanelV133.test.tsx"
    daily_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx"
    helper_source = helper_path.read_text(encoding="utf-8")
    panel_source = panel_path.read_text(encoding="utf-8")
    research_source = research_path.read_text(encoding="utf-8")
    daily_source = daily_path.read_text(encoding="utf-8")
    market_home_source = market_home_path.read_text(encoding="utf-8")
    home_page_source = home_page_path.read_text(encoding="utf-8")
    tests_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (helper_test_path, panel_test_path, daily_test_path)
    )

    yield frontend_contract(f"{helper_source}\n{panel_source}")
    yield privacy_cost_contract(f"{helper_source}\n{panel_source}\n{research_source}\n{daily_source}")
    yield scope_contract(helper_source, home_page_source)
    yield regression_tests_contract(tests_source)
    yield focused_vitest_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            helper_path,
            panel_path,
            research_path,
            daily_path,
            market_home_path,
            home_page_path,
            helper_test_path,
            panel_test_path,
            daily_test_path,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V133 local market-event follow-up loop."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_MARKET_EVENT_FOLLOW_UP_V133_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import re
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


def backend_contract(source: str, env_example: str, production_env: str) -> CheckResult:
    required = (
        'CNINFO_REPORT_URL = "https://www.cninfo.com.cn/new/information/getPrbookInfo"',
        'FOMC_CALENDAR_URL = "https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm"',
        'YAHOO_QUOTE_URL = "https://finance.yahoo.com/quote/{symbol}/"',
        "CALENDAR_PAST_DAYS = 7",
        "CALENDAR_FUTURE_DAYS = 30",
        "DEFAULT_MAX_EVENTS = 36",
        "DEFAULT_CACHE_TTL_SECONDS = 900",
        "DEFAULT_STALE_TTL_SECONDS = 21600",
        "DEFAULT_TIMEOUT_SECONDS = 4.0",
        'time_kind: str = "scheduled"',
        'classification_source: str = "provider_schedule"',
        "PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED",
        "_merge_events(scheduled_events, news_events)",
        "if len(merged) >= 48:",
    )
    missing = [token for token in required if token not in source]
    env_safe = (
        "PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED=false" in env_example
        and "PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED=false" in production_env
    )
    return CheckResult(
        "v135_sources_bounds_and_safe_flags",
        not missing and env_safe,
        {"missing": missing, "safe_default": env_safe},
    )


def cost_privacy_contract(source: str) -> CheckResult:
    lowered = source.casefold()
    forbidden = (
        "openai",
        "litellm",
        "deepseek",
        "ollama",
        "api_key",
        "platform_user_id",
        "database.",
        "session.add(",
        "sendemail",
        "sendsms",
        "pushnotification",
    )
    hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "v135_no_ai_key_database_or_notification",
        not hits,
        {"forbidden_hits": hits},
    )


def frontend_contract(source: str) -> CheckResult:
    required = (
        'data-testid="market-event-calendar-v135"',
        "今日",
        "本周",
        "我的日历",
        "待复盘",
        "Today",
        "This week",
        "My calendar",
        "Due",
        "公开数据 · 未使用 AI",
        "Public data · No AI used",
        "事件与行情并列展示不代表因果关系。",
        "Events and market prices shown together do not establish causality.",
        "仅提供资讯和数据，不构成投资建议。",
        "Information and data only. Not investment advice.",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("v135_bilingual_weekly_calendar", not missing, {"missing": missing})


def regression_tests_contract(source: str) -> CheckResult:
    normalized = source.replace("_", " ").casefold()
    required = (
        "builds scheduled events for three markets without forecast values",
        "marks memory cache and stale fallback per source",
        "timeout in one source does not block other market events",
        "v135 merges scheduled events first and deduplicates ids",
        "v135 calendar failure keeps news and adds truthful warning",
        "uses a provider scheduled timestamp directly without parsing the title",
        "defaults to this week and exposes today, mine, and due views in Chinese",
        "renders localized English event labels, source status, and query action",
        "adds and removes V135 follow-up calendar checkpoints with the V133 follow state",
    )
    missing = [token for token in required if token.casefold() not in normalized]
    return CheckResult("v135_regression_paths", not missing, {"missing": missing})


def guest_private_request_contract(home_source: str, watchlist_source: str) -> CheckResult:
    required_home = (
        "const privateWorkspaceEnabled = platformStatusLoaded",
        "&& (!platformEnabled || Boolean(platformSession))",
        "const legacyWorkspaceEnabled = platformStatusLoaded && !platformEnabled",
        "if (!privateWorkspaceEnabled) return undefined;",
        "if (!privateWorkspaceEnabled) return;",
        "if (!legacyWorkspaceEnabled) {",
        "enabled: privateWorkspaceEnabled",
        "const watchlistState = useWatchlist(privateWorkspaceEnabled)",
        "marketWorkspaceApi.getHome()",
    )
    required_watchlist = (
        "export function useWatchlist(enabled = true): UseWatchlistReturn",
        "if (!enabled) {",
        "if (!enabled || !stockCode || isActioning) return;",
    )
    missing = [
        token
        for token in required_home
        if token not in home_source
    ]
    missing.extend(
        token
        for token in required_watchlist
        if token not in watchlist_source
    )
    public_home_unguarded = bool(
        re.search(
            r"useEffect\(\(\) => \{\s+let active = true;\s+marketWorkspaceApi\.getHome\(\)",
            home_source,
        )
    )
    return CheckResult(
        "v135_guest_private_requests_dormant",
        not missing and public_home_unguarded,
        {
            "missing": missing,
            "public_home_unguarded": public_home_unguarded,
        },
    )


def _process_result(name: str, completed: subprocess.CompletedProcess[str]) -> CheckResult:
    output_lines = [
        line.strip()
        for line in f"{completed.stdout}\n{completed.stderr}".splitlines()
        if line.strip()
    ]
    return CheckResult(
        name,
        completed.returncode == 0,
        {
            "returncode": completed.returncode,
            "summary": " | ".join(output_lines[-7:]),
        },
    )


def focused_backend_check(repo_root: Path) -> CheckResult:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_public_market_calendar_service_v135",
            "tests.test_public_market_home_v116",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v135_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_executable is None:
        return CheckResult("v135_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm_executable,
            "test",
            "--",
            "--run",
            "src/components/market-home/__tests__/marketEventCalendarV134.test.ts",
            "src/components/market-home/__tests__/MarketEventCalendarPanelV135.test.tsx",
            "src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
            "src/pages/__tests__/HomePage.test.tsx",
            "src/hooks/__tests__/useWatchlist.test.tsx",
        ],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v135_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    service_path = repo_root / "src/services/public_market_calendar_service.py"
    home_service_path = repo_root / "src/services/public_market_home_service.py"
    schema_path = repo_root / "api/v1/schemas/market_workspace.py"
    env_path = repo_root / ".env.example"
    production_env_path = repo_root / "docs/superpowers/platform-production-env.example"
    panel_path = (
        repo_root
        / "apps/dsa-web/src/components/market-home/MarketEventCalendarPanelV135.tsx"
    )
    daily_path = (
        repo_root
        / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx"
    )
    model_path = (
        repo_root
        / "apps/dsa-web/src/components/market-home/marketEventCalendarV134.ts"
    )
    home_page_path = repo_root / "apps/dsa-web/src/pages/HomePage.tsx"
    watchlist_hook_path = repo_root / "apps/dsa-web/src/hooks/useWatchlist.ts"
    backend_test_paths = (
        repo_root / "tests/test_public_market_calendar_service_v135.py",
        repo_root / "tests/test_public_market_home_v116.py",
    )
    frontend_test_paths = (
        repo_root / "apps/dsa-web/src/components/market-home/__tests__/marketEventCalendarV134.test.ts",
        repo_root / "apps/dsa-web/src/components/market-home/__tests__/MarketEventCalendarPanelV135.test.tsx",
        repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
        repo_root / "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx",
        repo_root / "apps/dsa-web/src/hooks/__tests__/useWatchlist.test.tsx",
    )

    service_source = service_path.read_text(encoding="utf-8")
    home_source = home_service_path.read_text(encoding="utf-8")
    schema_source = schema_path.read_text(encoding="utf-8")
    panel_source = panel_path.read_text(encoding="utf-8")
    tests_source = "\n".join(
        path.read_text(encoding="utf-8")
        for path in (*backend_test_paths, *frontend_test_paths)
    )

    yield backend_contract(
        f"{service_source}\n{home_source}\n{schema_source}",
        env_path.read_text(encoding="utf-8"),
        production_env_path.read_text(encoding="utf-8"),
    )
    yield cost_privacy_contract(service_source)
    yield frontend_contract(panel_source)
    yield regression_tests_contract(tests_source)
    yield guest_private_request_contract(
        home_page_path.read_text(encoding="utf-8"),
        watchlist_hook_path.read_text(encoding="utf-8"),
    )
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            service_path,
            home_service_path,
            schema_path,
            panel_path,
            daily_path,
            model_path,
            home_page_path,
            watchlist_hook_path,
            *backend_test_paths,
            *frontend_test_paths,
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V135 real public market calendar and weekly views."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_REAL_MARKET_CALENDAR_V135_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

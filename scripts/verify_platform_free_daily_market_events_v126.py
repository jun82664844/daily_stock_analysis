from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable

REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_HOMEPAGE_BYTES = 500_000


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: Dict[str, Any]


def homepage_bundle_check(assets_dir: Path) -> CheckResult:
    chunks = list(assets_dir.glob("HomePage-*.js"))
    if not chunks:
        return CheckResult("homepage_bundle", False, {"reason": "homepage_chunk_missing"})
    newest = max(chunks, key=lambda path: path.stat().st_mtime_ns)
    size = newest.stat().st_size
    return CheckResult(
        "homepage_bundle",
        size < MAX_HOMEPAGE_BYTES,
        {"filename": newest.name, "size_bytes": size, "limit_bytes": MAX_HOMEPAGE_BYTES},
    )


def event_service_contract(source: str) -> CheckResult:
    required = (
        "PublicMarketEventService",
        "keyword_rules",
        "earnings",
        "announcement",
        "dividend",
        "trading_status",
        "macro",
        "corporate",
        "market",
        "A_SHARE_SYMBOL_PATTERN",
        "HK_SYMBOL_PATTERN",
        "_symbol_in_title",
        "factory orders",
    )
    forbidden = ("import requests", "import httpx", "openai", "litellm", "ollama")
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source.casefold()]
    return CheckResult(
        "no_ai_event_service",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def frontend_contract(public_home_source: str, home_page_source: str) -> CheckResult:
    required_public = (
        "const DailyMarketEventCenterV126 = lazy(() => import(",
        "events={data.events}",
        "watchlistSymbols={watchlistSymbols}",
    )
    required_home = (
        "watchlistSymbols={platformWatchlistItems.map((item) => item.stockCode)}",
    )
    forbidden_home = ("events: platformWatchlistItems", "getHome(platformWatchlistItems")
    missing = [token for token in required_public if token not in public_home_source]
    missing.extend(token for token in required_home if token not in home_page_source)
    forbidden_hits = [token for token in forbidden_home if token in home_page_source]
    return CheckResult(
        "lazy_private_watchlist_context",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def safety_regression_contract(event_test_source: str, component_source: str, component_test_source: str) -> CheckResult:
    required_event_tests = (
        "test_does_not_link_ambiguous_short_us_symbols_without_cashtag",
        "test_macro_rules_win_over_buyback_and_order_terms",
        "test_explicit_exchange_symbol_overrides_mixed_feed_market",
        "test_deduplicates_prioritizes_published_time_and_preserves_retrieved_time",
    )
    required_component_tests = (
        "offers a market-update filter and labels unlinked markets as source channels",
    )
    missing = [token for token in required_event_tests if token not in event_test_source]
    missing.extend(token for token in required_component_tests if token not in component_test_source)
    if "sourceMarkets" not in component_source:
        missing.append("component:sourceMarkets")
    if "const FILTERS" not in component_source:
        missing.append("component:const FILTERS")
    else:
        filters_segment = component_source.split("const FILTERS", 1)[1].split(";", 1)[0]
        if "'market'" not in filters_segment:
            missing.append("component:FILTERS.market")
    return CheckResult("review_safety_regressions", not missing, {"missing": missing})


def source_contract(repo_root: Path) -> CheckResult:
    files = {
        "schema": repo_root / "api/v1/schemas/market_workspace.py",
        "home_service": repo_root / "src/services/public_market_home_service.py",
        "component": repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx",
    }
    required = {
        "schema": ("PublicMarketEvent", "MarketEventCategory", "classification_source"),
        "home_service": ("event_builder", "market_events_unavailable", '"events": events'),
        "component": ("今日市场事件", "Daily market events", "不构成投资建议", "Not investment advice", "sourceState.status"),
    }
    missing: list[str] = []
    for key, path in files.items():
        if not path.exists():
            missing.append(str(path.relative_to(repo_root)))
            continue
        source = path.read_text(encoding="utf-8")
        missing.extend(
            f"{path.relative_to(repo_root)}:{token}"
            for token in required[key]
            if token not in source
        )
    return CheckResult("v126_source_contract", not missing, {"missing": missing})


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    event_source = (repo_root / "src/services/public_market_event_service.py").read_text(encoding="utf-8")
    public_home_source = (repo_root / "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx").read_text(encoding="utf-8")
    home_page_source = (repo_root / "apps/dsa-web/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    event_test_source = (repo_root / "tests/test_public_market_event_service.py").read_text(encoding="utf-8")
    component_source = (repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx").read_text(encoding="utf-8")
    component_test_source = (repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx").read_text(encoding="utf-8")
    yield event_service_contract(event_source)
    yield frontend_contract(public_home_source, home_page_source)
    yield safety_regression_contract(event_test_source, component_source, component_test_source)
    yield source_contract(repo_root)
    yield homepage_bundle_check(repo_root / "static/assets")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V126 free daily market events.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_FREE_DAILY_MARKET_EVENTS_V126_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

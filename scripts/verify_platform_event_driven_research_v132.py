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


def frontend_contract(source: str) -> CheckResult:
    required = (
        'data-testid="market-event-research-panel-v132"',
        'data-testid="market-event-public-quote-v132"',
        'data-testid="market-event-quote-unavailable-v132"',
        "research: '研究事件'",
        "research: 'Research event'",
        "事件研究卡 · 未使用 AI",
        "Event research card · No AI used",
        "价格变化与事件同时呈现，不代表事件导致涨跌。",
        "Price changes and the event are shown together; this does not mean the event caused the move.",
        "仅提供公开资讯和数据，不构成投资建议。",
        "Public information and data only. Not investment advice.",
    )
    missing = [token for token in required if token not in source]
    return CheckResult("event_research_frontend", not missing, {"missing": missing})


def privacy_cost_contract(source: str) -> CheckResult:
    forbidden = (
        "fetch(",
        "axios",
        "apiclient",
        "marketworkspaceapi",
        "openai",
        "litellm",
        "ollama",
        "platform_user_id",
        "email",
    )
    lowered = source.casefold()
    forbidden_hits = [token for token in forbidden if token in lowered]
    return CheckResult(
        "no_new_network_ai_or_tracking",
        not forbidden_hits,
        {"forbidden_hits": forbidden_hits},
    )


def regression_tests_contract(source: str) -> CheckResult:
    required = (
        "opens a no-AI event research card with linked public market context",
        "degrades honestly when linked quote context is unavailable and shows a research checklist",
        "getByRole('button', { name: '研究 AAPL 关联事件' })",
        "getByTestId('market-event-research-panel-v132')",
    )
    missing = [token for token in required if token not in source]
    degraded_path_evidence = any(
        token in source
        for token in (
            "getByTestId('market-event-quote-unavailable-v132')",
            "queryByTestId('market-event-public-quote-v132')",
        )
    )
    if not degraded_path_evidence:
        missing.append("degraded quote path assertion")
    return CheckResult("v132_regression_tests", not missing, {"missing": missing})


def wiring_contract(daily_source: str, home_source: str) -> CheckResult:
    required = (
        "marketItems?: MarketSecurityItem[]",
        "const marketItemBySymbol = useMemo",
        "normalizeMarketEventSymbol(item.symbol)",
        "normalizeMarketEventSymbol(event.symbol)",
        "<MarketEventResearchPanelV132",
        "marketItems={marketItems}",
        "...(section.mostActive ?? [])",
        "...(section.gainers ?? [])",
        "...(section.losers ?? [])",
    )
    combined = f"{daily_source}\n{home_source}"
    missing = [token for token in required if token not in combined]
    return CheckResult("three_market_public_data_wiring", not missing, {"missing": missing})


def homepage_bundle_check(assets_dir: Path, *, source_paths: Iterable[Path] = ()) -> CheckResult:
    chunks = list(assets_dir.glob("HomePage-*.js"))
    if not chunks:
        return CheckResult("homepage_bundle", False, {"reason": "homepage_chunk_missing"})
    newest = max(chunks, key=lambda path: path.stat().st_mtime_ns)
    existing_sources = [path for path in source_paths if path.exists()]
    latest_source_mtime_ns = max((path.stat().st_mtime_ns for path in existing_sources), default=0)
    size = newest.stat().st_size
    bundle_fresh = newest.stat().st_mtime_ns >= latest_source_mtime_ns
    return CheckResult(
        "homepage_bundle",
        size < MAX_HOMEPAGE_BYTES and bundle_fresh,
        {
            "filename": newest.name,
            "size_bytes": size,
            "limit_bytes": MAX_HOMEPAGE_BYTES,
            "bundle_fresh": bundle_fresh,
        },
    )


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    daily_path = repo_root / "apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx"
    panel_path = repo_root / "apps/dsa-web/src/components/market-home/MarketEventResearchPanelV132.tsx"
    home_path = repo_root / "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx"
    test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx"
    daily_source = daily_path.read_text(encoding="utf-8")
    panel_source = panel_path.read_text(encoding="utf-8")
    home_source = home_path.read_text(encoding="utf-8")
    test_source = test_path.read_text(encoding="utf-8")

    yield frontend_contract(f"{daily_source}\n{panel_source}")
    yield wiring_contract(daily_source, home_source)
    yield privacy_cost_contract(panel_source)
    yield regression_tests_contract(test_source)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(daily_path, panel_path, home_path, test_path),
    )


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V132 event-driven public research loop.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_EVENT_DRIVEN_RESEARCH_V132_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

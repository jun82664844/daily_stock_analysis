from __future__ import annotations

import argparse
import re
import shutil
import subprocess
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


def market_items_wiring_block(home_source: str) -> str:
    start = "const marketItems = useMemo"
    end = "const selectedAlertItem"
    if start not in home_source:
        return ""
    block = home_source.split(start, 1)[1]
    return block.split(end, 1)[0]


def frontend_safety_contract(daily_source: str, panel_source: str, home_source: str) -> CheckResult:
    return privacy_cost_contract(
        f"{daily_source}\n{panel_source}\n{market_items_wiring_block(home_source)}"
    )


def regression_tests_contract(source: str) -> CheckResult:
    required = (
        "opens a no-AI event research card with linked public market context",
        "shows localized unavailable text when a linked quote field is missing",
        "degrades honestly when linked quote context is unavailable and shows a research checklist",
        "does not use a market index quote as linked-security research context",
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
    return CheckResult("v132_regression_test_contract", not missing, {"missing": missing})


def focused_vitest_check(repo_root: Path) -> CheckResult:
    npm_executable = shutil.which("npm.cmd") or shutil.which("npm")
    if npm_executable is None:
        return CheckResult("v132_focused_vitest", False, {"reason": "npm_not_found"})
    test_files = (
        "src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
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
        "v132_focused_vitest",
        completed.returncode == 0,
        {
            "returncode": completed.returncode,
            "test_files": list(test_files),
            "summary": " | ".join(output_lines[-6:]),
        },
    )


def wiring_contract(daily_source: str, home_source: str) -> CheckResult:
    required = (
        "marketItems?: MarketSecurityItem[]",
        "const marketItemBySymbol = useMemo",
        "normalizeMarketEventSymbol(item.symbol)",
        "normalizeMarketEventSymbol(event.symbol)",
        "<MarketEventResearchPanelV132",
        "marketItems={marketItems}",
        "...section.attention,",
        "...(section.mostActive ?? [])",
        "...(section.gainers ?? [])",
        "...(section.losers ?? [])",
    )
    combined = f"{daily_source}\n{home_source}"
    missing = [token for token in required if token not in combined]
    market_items_block = market_items_wiring_block(home_source)
    forbidden_hits = [
        token for token in ("...section.indices",)
        if token in market_items_block
    ]
    return CheckResult(
        "three_market_public_data_wiring",
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def homepage_bundle_check(assets_dir: Path, *, source_paths: Iterable[Path] = ()) -> CheckResult:
    index_html = assets_dir.parent / "index.html"
    if not index_html.is_file():
        return CheckResult("homepage_bundle", False, {"reason": "index_html_missing"})
    entry_match = re.search(
        r"/assets/(?P<entry>index-[A-Za-z0-9_-]+\.js)",
        index_html.read_text(encoding="utf-8"),
    )
    if entry_match is None:
        return CheckResult("homepage_bundle", False, {"reason": "current_entry_missing"})
    entry_path = assets_dir / entry_match.group("entry")
    if not entry_path.is_file():
        return CheckResult(
            "homepage_bundle",
            False,
            {"reason": "current_entry_asset_missing", "entry": entry_path.name},
        )
    home_match = re.search(
        r"(?P<chunk>HomePage-[A-Za-z0-9_-]+\.js)",
        entry_path.read_text(encoding="utf-8"),
    )
    if home_match is None:
        return CheckResult(
            "homepage_bundle",
            False,
            {"reason": "current_homepage_reference_missing", "entry": entry_path.name},
        )
    current = assets_dir / home_match.group("chunk")
    if not current.is_file():
        return CheckResult(
            "homepage_bundle",
            False,
            {"reason": "current_homepage_chunk_missing", "filename": current.name},
        )
    existing_sources = [path for path in source_paths if path.exists()]
    latest_source_mtime_ns = max((path.stat().st_mtime_ns for path in existing_sources), default=0)
    size = current.stat().st_size
    bundle_fresh = current.stat().st_mtime_ns >= latest_source_mtime_ns
    return CheckResult(
        "homepage_bundle",
        size < MAX_HOMEPAGE_BYTES and bundle_fresh,
        {
            "filename": current.name,
            "entry": entry_path.name,
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
    home_test_path = repo_root / "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx"
    daily_source = daily_path.read_text(encoding="utf-8")
    panel_source = panel_path.read_text(encoding="utf-8")
    home_source = home_path.read_text(encoding="utf-8")
    test_source = test_path.read_text(encoding="utf-8")
    home_test_source = home_test_path.read_text(encoding="utf-8")

    yield frontend_contract(f"{daily_source}\n{panel_source}")
    yield wiring_contract(daily_source, home_source)
    yield frontend_safety_contract(daily_source, panel_source, home_source)
    yield regression_tests_contract(f"{test_source}\n{home_test_source}")
    yield focused_vitest_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(daily_path, panel_path, home_path, test_path, home_test_path),
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

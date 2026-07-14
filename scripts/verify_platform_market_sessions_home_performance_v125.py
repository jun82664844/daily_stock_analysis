from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable


REPO_ROOT = Path(__file__).resolve().parents[1]
MAX_HOMEPAGE_BYTES = 500_000
LAZY_COMPONENTS = (
    "DecisionJourneyV91",
    "FreeApiTrialPanelV93",
    "WatchlistEventRadarV99",
    "DailyResearchCockpitV103",
    "GlobalEquityEnrichmentCard",
)


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


def lazy_component_contract(source: str) -> CheckResult:
    missing = [
        name for name in LAZY_COMPONENTS
        if f"const {name} = lazy(() => import(" not in source
    ]
    return CheckResult("query_feature_lazy_loading", not missing, {"missing": missing})


def source_contract(repo_root: Path) -> CheckResult:
    files = {
        "session_service": repo_root / "src/services/public_market_session_service.py",
        "schema": repo_root / "api/v1/schemas/market_workspace.py",
        "workbench": repo_root / "apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx",
    }
    required = {
        "session_service": ("exchange_calendar", "session_phase", "minutes_to_open", "minutes_to_close"),
        "schema": ("MarketSessionPhase", "session_warning_codes"),
        "workbench": ("Exchange calendar", "交易所日历", "countdownLabel"),
    }
    missing = []
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
    return CheckResult("market_session_source_contract", not missing, {"missing": missing})


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    home_source = (repo_root / "apps/dsa-web/src/pages/HomePage.tsx").read_text(encoding="utf-8")
    yield source_contract(repo_root)
    yield lazy_component_contract(home_source)
    yield homepage_bundle_check(repo_root / "static/assets")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify DSA V125 market sessions and home performance.")
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_MARKET_SESSIONS_HOME_PERFORMANCE_V125_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

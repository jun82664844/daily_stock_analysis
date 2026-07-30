from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_platform_event_driven_research_v132 import homepage_bundle_check


@dataclass(frozen=True)
class CheckResult:
    name: str
    ok: bool
    details: Dict[str, Any]


def _tokens(
    name: str,
    source: str,
    required: Sequence[str],
    forbidden: Sequence[str] = (),
) -> CheckResult:
    missing = [token for token in required if token not in source]
    forbidden_hits = [token for token in forbidden if token in source]
    return CheckResult(
        name,
        not missing and not forbidden_hits,
        {"missing": missing, "forbidden_hits": forbidden_hits},
    )


def run_static_checks(repo_root: Path) -> Iterable[CheckResult]:
    service = (
        repo_root / "src/services/public_symbol_event_archive_service.py"
    ).read_text(encoding="utf-8")
    reaction = (
        repo_root / "src/services/public_market_event_reaction_service.py"
    ).read_text(encoding="utf-8")
    calendar = (
        repo_root / "src/services/public_market_calendar_service.py"
    ).read_text(encoding="utf-8")
    endpoint = (
        repo_root / "api/v1/endpoints/market_workspace.py"
    ).read_text(encoding="utf-8")
    schema = (
        repo_root / "api/v1/schemas/market_workspace.py"
    ).read_text(encoding="utf-8")
    frontend_api = (
        repo_root / "apps/dsa-web/src/api/marketWorkspace.ts"
    ).read_text(encoding="utf-8")
    page = (
        repo_root / "apps/dsa-web/src/pages/MarketWorkspacePage.tsx"
    ).read_text(encoding="utf-8")
    panel = (
        repo_root
        / "apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx"
    ).read_text(encoding="utf-8")
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    production = (
        repo_root / "docs/superpowers/platform-production-env.example"
    ).read_text(encoding="utf-8")

    yield _tokens(
        "v139_single_symbol_archive_service",
        service,
        (
            "_MONTH_TO_DAYS = {6: 183, 12: 366, 24: 732}",
            'str(event.get("symbol")',
            "include_observed_history=True",
            "max_events=48",
            "observe_events(events, max_events=24)",
            "event_price_observation_unavailable",
            "causality_disclaimer",
            "ai_used",
            "informational_only",
            "_safe_http_url",
        ),
        forbidden=(
            "from litellm",
            "import openai",
            "from openai",
            "import ollama",
            "platform_identity_from_request",
            "api_key",
        ),
    )
    yield _tokens(
        "v139_bounded_two_year_observations",
        f"{calendar}\n{reaction}",
        (
            "MAX_HISTORICAL_PAST_DAYS = 760",
            '"range": "2y"',
            "[-560:]",
            "def observe_events(",
            "balance_markets=False",
            "min(int(max_events or self.max_events), 24)",
        ),
    )
    yield _tokens(
        "v139_public_api_contract",
        f"{endpoint}\n{schema}\n{frontend_api}",
        (
            "PLATFORM_PUBLIC_SYMBOL_EVENT_ARCHIVE_V139_ENABLED",
            "market_workspace_symbol_event_archive",
            "PublicSymbolEventArchiveResponse",
            "/event-archive",
            "getSymbolEventArchive",
            "withCredentials: false",
            "causalityDisclaimer",
        ),
    )
    yield _tokens(
        "v139_bilingual_information_only_ui",
        f"{page}\n{panel}",
        (
            "个股事件档案",
            "Symbol event archive",
            "MONTHS: Months[] = [6, 12, 24]",
            "档案时间范围",
            "Archive range",
            "同期变化不代表事件导致价格变化",
            "Same-period changes do not establish",
            "只提供资讯和客观数据",
            "Not investment advice",
            "查看来源",
            "Open source",
        ),
        forbidden=(
            "建议买入",
            "建议卖出",
            "guaranteed return",
        ),
    )
    safe_defaults = all(
        "PLATFORM_PUBLIC_SYMBOL_EVENT_ARCHIVE_V139_ENABLED=false" in content
        and "PLATFORM_RATE_LIMIT_MARKET_WORKSPACE_SYMBOL_EVENT_ARCHIVE_MAX=30" in content
        for content in (env_example, production)
    )
    yield CheckResult(
        "v139_production_safe_defaults",
        safe_defaults,
        {"safe_defaults": safe_defaults},
    )


def _process_result(
    name: str,
    completed: subprocess.CompletedProcess[str],
) -> CheckResult:
    lines = [
        line.strip()
        for line in f"{completed.stdout}\n{completed.stderr}".splitlines()
        if line.strip()
    ]
    return CheckResult(
        name,
        completed.returncode == 0,
        {
            "returncode": completed.returncode,
            "summary": " | ".join(lines[-8:]),
        },
    )


def focused_backend_check(repo_root: Path) -> CheckResult:
    completed = subprocess.run(
        [
            sys.executable,
            "-m",
            "unittest",
            "tests.test_public_symbol_event_archive_v139",
            "tests.test_public_event_history_coverage_v138",
            "tests.test_public_market_event_reaction_service_v136",
            "tests.test_public_market_event_reaction_api_v136",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v139_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        return CheckResult("v139_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm,
            "test",
            "--",
            "--run",
            "src/components/market-workspace/SymbolEventArchiveV139.test.tsx",
            "src/pages/__tests__/MarketWorkspacePage.test.tsx",
        ],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v139_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    yield from run_static_checks(repo_root)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "src/services/public_symbol_event_archive_service.py",
            repo_root / "api/v1/endpoints/market_workspace.py",
            repo_root / "api/v1/schemas/market_workspace.py",
            repo_root / "apps/dsa-web/src/api/marketWorkspace.ts",
            repo_root / "apps/dsa-web/src/pages/MarketWorkspacePage.tsx",
            repo_root
            / "apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V139 public symbol event archive."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_SYMBOL_EVENT_ARCHIVE_V139_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

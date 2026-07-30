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
    calendar = (
        repo_root / "src/services/public_market_calendar_service.py"
    ).read_text(encoding="utf-8")
    reaction = (
        repo_root / "src/services/public_market_event_reaction_service.py"
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
    panel = (
        repo_root
        / "apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx"
    ).read_text(encoding="utf-8")
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    production = (
        repo_root / "docs/superpowers/platform-production-env.example"
    ).read_text(encoding="utf-8")

    yield _tokens(
        "v138_cninfo_and_public_corporate_event_history",
        calendar,
        (
            "corporate_action_loader",
            "def _build_yahoo_corporate_action_events(",
            "def _fetch_yahoo_corporate_actions(",
            '"yahoo_chart_corporate_actions"',
            '"cninfo_report_history"',
            '"provider_event_history"',
            'time_kind="observed"',
            "MAX_HISTORICAL_PAST_DAYS = 400",
            "event_symbol not in visible_symbols",
            '"range": "1y"',
            "MAX_CORPORATE_ACTION_RESPONSE_BYTES",
        ),
        forbidden=(
            "from litellm",
            "import openai",
            "from openai",
            "import ollama",
        ),
    )
    yield _tokens(
        "v138_balanced_observation_contract",
        reaction,
        (
            "allow_event_history",
            "PLATFORM_PUBLIC_EVENT_HISTORY_V138_ENABLED",
            'classification_source == "provider_event_history"',
            'time_kind == "observed"',
            'for market in ("cn", "hk", "us")',
            '"event_time_kind"',
            '"classification_source"',
            'params={"interval": "1d", "range": "1y", "events": "history"}',
            "[-320:]",
        ),
        forbidden=(
            "from litellm",
            "import openai",
            "from openai",
            "import ollama",
        ),
    )
    yield _tokens(
        "v138_endpoint_and_schema",
        f"{endpoint}\n{schema}\n{frontend_api}",
        (
            "PLATFORM_PUBLIC_EVENT_HISTORY_V138_ENABLED",
            "PLATFORM_PUBLIC_EVENT_HISTORY_V138_PAST_DAYS",
            "include_observed_history=event_history_enabled",
            '"provider_event_history"',
            "event_time_kind",
            '"stock_split"',
            "eventTimeKind",
            "classificationSource",
        ),
    )
    yield _tokens(
        "v138_bilingual_information_only_ui",
        panel,
        (
            "来源计划日期",
            "来源历史事件",
            "Source-scheduled date",
            "Recorded historical event",
            "巨潮资讯 / Yahoo 公开日历与图表",
            "CNInfo / Yahoo public calendar and chart",
            "同期表现不代表事件导致行情变化",
            "Same-period performance does not establish",
        ),
        forbidden=(
            "建议买入",
            "建议卖出",
            "目标价",
            "guaranteed return",
        ),
    )
    safe_defaults = all(
        token in content
        for content in (env_example, production)
        for token in (
            "PLATFORM_PUBLIC_EVENT_HISTORY_V138_ENABLED=false",
            "PLATFORM_PUBLIC_EVENT_HISTORY_V138_PAST_DAYS=180",
        )
    )
    yield CheckResult(
        "v138_production_safe_defaults",
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
            "tests.test_public_event_history_coverage_v138",
            "tests.test_public_market_calendar_service_v135",
            "tests.test_public_market_event_reaction_service_v136",
            "tests.test_public_event_reaction_availability_v137",
            "tests.test_public_market_event_reaction_api_v136",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v138_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        return CheckResult(
            "v138_focused_frontend",
            False,
            {"reason": "npm_not_found"},
        )
    completed = subprocess.run(
        [
            npm,
            "test",
            "--",
            "--run",
            "src/api/__tests__/marketWorkspace.test.ts",
            (
                "src/components/market-home/__tests__/"
                "MarketEventReactionPanelV136.test.tsx"
            ),
        ],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v138_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    yield from run_static_checks(repo_root)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "src/services/public_market_calendar_service.py",
            repo_root / "src/services/public_market_event_reaction_service.py",
            repo_root / "api/v1/endpoints/market_workspace.py",
            repo_root / "api/v1/schemas/market_workspace.py",
            repo_root / "apps/dsa-web/src/api/marketWorkspace.ts",
            repo_root
            / "apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V138 CN/HK public event-history coverage."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_EVENT_HISTORY_COVERAGE_V138_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

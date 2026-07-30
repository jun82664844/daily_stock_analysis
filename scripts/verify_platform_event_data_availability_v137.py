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
    hits = [token for token in forbidden if token in source]
    return CheckResult(
        name,
        not missing and not hits,
        {"missing": missing, "forbidden_hits": hits},
    )


def run_static_checks(repo_root: Path) -> Iterable[CheckResult]:
    cache = (
        repo_root / "src/services/public_event_reaction_cache.py"
    ).read_text(encoding="utf-8")
    service = (
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
    panel = (
        repo_root
        / "apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx"
    ).read_text(encoding="utf-8")
    env_example = (repo_root / ".env.example").read_text(encoding="utf-8")
    production = (
        repo_root / "docs/superpowers/platform-production-env.example"
    ).read_text(encoding="utf-8")

    yield _tokens(
        "v137_versioned_atomic_public_snapshot",
        cache,
        (
            "SNAPSHOT_VERSION = 1",
            "DEFAULT_MAX_BYTES = 1024 * 1024",
            "_FORBIDDEN_KEYS",
            'value.get("ai_used") is not False',
            'value.get("informational_only") is not True',
            "temp_path.replace(self.path)",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_PATH",
        ),
    )
    yield _tokens(
        "v137_cache_first_single_flight",
        service,
        (
            "def build(self, *, cache_first: bool = False)",
            "def _build_cache_first(self)",
            "def _start_background_refresh(self)",
            "self._refresh_future is not None and not self._refresh_future.done()",
            "def wait_for_refresh(",
            "self.snapshot_store.write(payload)",
            '"event_reaction_refreshing"',
            '"event_reaction_response_stale"',
        ),
        forbidden=(
            "from litellm",
            "import openai",
            "from openai",
            "import ollama",
        ),
    )
    yield _tokens(
        "v137_independent_market_refresh_and_inflight_reuse",
        f"{calendar}\n{endpoint}",
        (
            "self._inflight",
            'jobs[f"yahoo:{market}:{symbol}{suffix}"]',
            "_EVENT_REACTION_LOADER_EXECUTOR",
            "_EVENT_REACTION_DEFAULT_SECTIONS",
            '"market_sources": market_sources',
            '"event_calendar_market_unavailable"',
            "prewarm_public_event_reactions",
        ),
    )
    loader_start = endpoint.find("def _load_event_reaction_events():")
    loader_end = endpoint.find("\n\n_public_event_reaction_service", loader_start)
    loader = endpoint[loader_start:loader_end]
    yield CheckResult(
        "v137_cold_loader_skips_full_home_build",
        loader_start >= 0
        and "_public_home_service.build()" not in loader
        and "past_days=45" in loader
        and "include_historical=True" in loader,
        {"loader_found": loader_start >= 0},
    )
    yield _tokens(
        "v137_schema_and_bilingual_frontend",
        f"{schema}\n{frontend_api}\n{panel}",
        (
            "class EventReactionCacheState",
            "class EventReactionMarketSource",
            "market_sources: List[EventReactionMarketSource]",
            "marketSources: EventReactionMarketSource[]",
            'data-testid="event-reaction-market-sources-v137"',
            "三市场数据可用性",
            "Three-market data availability",
            "正在后台刷新公开事件数据",
            "Refreshing public event data in the background",
            "磁盘快照",
            "Disk snapshot",
            "pollAttempts.current >= 6",
            "payload && (payload.aiUsed || !payload.informationalOnly)",
        ),
    )
    safe_defaults = all(
        token in content
        for content in (env_example, production)
        for token in (
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_FIRST_ENABLED=false",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_CACHE_PATH=local/public_event_reactions_v137.json",
            "PLATFORM_PUBLIC_EVENT_REACTIONS_V137_DISK_STALE_TTL_SECONDS=86400",
        )
    )
    yield CheckResult(
        "v137_production_safe_defaults",
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
            "tests.test_public_event_reaction_cache_v137",
            "tests.test_public_event_reaction_availability_v137",
            "tests.test_public_event_reaction_startup_v137",
            "tests.test_public_market_event_reaction_service_v136",
            "tests.test_public_market_event_reaction_api_v136",
            "tests.test_public_market_calendar_service_v135",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v137_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        return CheckResult("v137_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm,
            "test",
            "--",
            "--run",
            "src/api/__tests__/marketWorkspace.test.ts",
            "src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx",
        ],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v137_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    yield from run_static_checks(repo_root)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "src/services/public_event_reaction_cache.py",
            repo_root / "src/services/public_market_event_reaction_service.py",
            repo_root / "src/services/public_market_calendar_service.py",
            repo_root / "api/v1/endpoints/market_workspace.py",
            repo_root / "api/v1/schemas/market_workspace.py",
            repo_root / "api/app.py",
            repo_root / "apps/dsa-web/src/api/marketWorkspace.ts",
            repo_root
            / "apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V137 event data availability and cold-start cache."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_EVENT_DATA_AVAILABILITY_V137_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
    reaction = (
        repo_root / "src/services/public_market_event_reaction_service.py"
    ).read_text(encoding="utf-8")
    archive = (
        repo_root / "src/services/public_symbol_event_archive_service.py"
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
    archive_panel = (
        repo_root
        / "apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx"
    ).read_text(encoding="utf-8")
    timeline = (
        repo_root
        / "apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.tsx"
    ).read_text(encoding="utf-8")

    yield _tokens(
        "v140_bounded_exact_date_chart",
        reaction,
        (
            "def load_price_chart(",
            "bounded_days = max(1, min(int(days), 760))",
            "bounded_points = max(2, min(int(max_points), 560))",
            "benchmark_by_date = {",
            "benchmark_row = benchmark_by_date.get(row_date)",
            '"benchmark_history_date_mismatch"',
            '"relative_change_percent"',
            '"volume": row.get("volume")',
        ),
        forbidden=(
            "forward_fill",
            "backfill",
            "fillna",
        ),
    )
    yield _tokens(
        "v140_three_market_benchmarks",
        reaction,
        (
            '"cn": ("000001.SS",',
            '"hk": ("^HSI",',
            '"us": ("^GSPC",',
        ),
    )
    yield _tokens(
        "v140_single_archive_response_contract",
        f"{archive}\n{endpoint}\n{schema}\n{frontend_api}",
        (
            "max_points=560",
            '"chart": chart',
            "PublicSymbolEventChartPoint",
            "PublicSymbolEventChart",
            "chart: PublicSymbolEventChart",
            "PublicSymbolEventArchiveResponse",
            "/event-archive",
            "withCredentials: false",
        ),
    )
    yield _tokens(
        "v140_event_linked_bilingual_chart",
        f"{archive_panel}\n{timeline}",
        (
            "SymbolEventTimelineV140",
            "LineChart",
            "ReferenceArea",
            "ReferenceLine",
            "Normalized performance (range start = 0)",
            "Event and price timeline",
            "事件与K线联动图",
            "does not establish that an event caused",
            "Not investment advice",
        ),
        forbidden=(
            "target price",
            "guaranteed return",
            "buy signal",
            "sell signal",
        ),
    )
    yield _tokens(
        "v140_degraded_without_fabrication",
        f"{reaction}\n{archive}\n{timeline}",
        (
            '"status": "unavailable"',
            '"points": []',
            '"benchmark_history_unavailable"',
            '"symbol_event_timeline_unavailable"',
            "Benchmark history is unavailable. The symbol series remains visible.",
            "Historical prices are temporarily unavailable.",
            "connectNulls={false}",
        ),
    )
    yield _tokens(
        "v140_public_no_ai_boundary",
        f"{reaction}\n{archive}\n{timeline}",
        (
            '"ai_used": False',
            '"informational_only": True',
            '"causality_disclaimer": True',
            "DSA V140",
            "No AI",
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
            "tests.test_public_symbol_event_timeline_v140",
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
    return _process_result("v140_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        return CheckResult("v140_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm,
            "test",
            "--",
            "--run",
            "src/components/market-workspace/SymbolEventTimelineV140.test.tsx",
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
    return _process_result("v140_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    yield from run_static_checks(repo_root)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "src/services/public_market_event_reaction_service.py",
            repo_root / "src/services/public_symbol_event_archive_service.py",
            repo_root / "api/v1/schemas/market_workspace.py",
            repo_root / "apps/dsa-web/src/api/marketWorkspace.ts",
            repo_root
            / "apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx",
            repo_root
            / "apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V140 event and price timeline."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_EVENT_KLINE_TIMELINE_V140_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

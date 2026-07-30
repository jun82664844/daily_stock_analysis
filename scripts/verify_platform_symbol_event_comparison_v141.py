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
    comparison = (
        repo_root
        / "apps/dsa-web/src/components/market-workspace/SymbolEventComparisonV141.tsx"
    ).read_text(encoding="utf-8")

    yield _tokens(
        "v141_bounded_descriptive_statistics",
        archive,
        (
            "_COMPARISON_WINDOWS = (1, 3, 5, 20)",
            "def _comparison_summaries(",
            "def _comparison_window(",
            "median(values)",
            '"sample_size"',
            '"benchmark_sample_size"',
            '"relative_sample_size"',
            '"positive_count"',
            '"negative_count"',
            '"flat_count"',
            '"completeness_percent"',
        ),
        forbidden=(
            "win_rate",
            "success_rate",
            "prediction_score",
        ),
    )
    yield _tokens(
        "v141_rejects_invalid_and_missing_samples",
        archive,
        (
            "isinstance(value, bool)",
            "math.isfinite(number)",
            "return None",
            "if symbol_value is not None:",
            "if benchmark_value is not None:",
            "if relative_value is not None:",
        ),
        forbidden=(
            "or 0.0",
            "fillna",
            "forward_fill",
        ),
    )
    yield _tokens(
        "v141_single_archive_response_contract",
        f"{archive}\n{endpoint}\n{schema}\n{frontend_api}",
        (
            '"comparison_summaries": comparison_summaries',
            "PublicSymbolEventComparisonWindow",
            "PublicSymbolEventComparisonSummary",
            "comparison_summaries:",
            "comparisonSummaries:",
            "/event-archive",
            "withCredentials: false",
        ),
    )
    yield _tokens(
        "v141_bilingual_linked_research_table",
        f"{archive_panel}\n{timeline}\n{comparison}",
        (
            "SymbolEventComparisonV141",
            "selectedEventId",
            "onSelectEvent",
            "sameTypeEvents",
            "Same-type event comparison",
            "同类事件历史对比",
            "historical distribution does not predict future performance",
            "历史分布不代表未来表现",
        ),
        forbidden=(
            "Buy now",
            "Sell now",
            "Target price",
            "Guaranteed return",
        ),
    )
    yield _tokens(
        "v141_honest_limited_and_empty_states",
        comparison,
        (
            "windowSummary.sampleSize < 3",
            "Limited sample",
            "样本有限",
            "No historical observations are available for this window.",
            "当前窗口暂无可用历史样本。",
            "symbolMedianReturnPercent",
            "relativeMedianReturnPercent",
        ),
    )
    yield _tokens(
        "v141_public_no_ai_and_safety_boundary",
        f"{archive}\n{comparison}",
        (
            '"ai_used": False',
            '"informational_only": True',
            '"causality_disclaimer": True',
            "DSA V141",
            "No AI",
            "does not predict future performance or establish causality",
            "Not investment advice",
            "不构成投资建议",
        ),
        forbidden=(
            "from litellm",
            "import openai",
            "from openai",
            "import ollama",
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
            "tests.test_public_symbol_event_comparison_v141",
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
    return _process_result("v141_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        return CheckResult("v141_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm,
            "test",
            "--",
            "--run",
            "src/components/market-workspace/SymbolEventComparisonV141.test.tsx",
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
    return _process_result("v141_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    yield from run_static_checks(repo_root)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)
    yield homepage_bundle_check(
        repo_root / "static/assets",
        source_paths=(
            repo_root / "src/services/public_symbol_event_archive_service.py",
            repo_root / "api/v1/schemas/market_workspace.py",
            repo_root / "apps/dsa-web/src/api/marketWorkspace.ts",
            repo_root
            / "apps/dsa-web/src/components/market-workspace/SymbolEventArchiveV139.tsx",
            repo_root
            / "apps/dsa-web/src/components/market-workspace/SymbolEventTimelineV140.tsx",
            repo_root
            / "apps/dsa-web/src/components/market-workspace/SymbolEventComparisonV141.tsx",
        ),
    )


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V141 same-type symbol event comparison."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_SYMBOL_EVENT_COMPARISON_V141_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

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
        repo_root / "src/services/public_stock_research_overview_service.py"
    ).read_text(encoding="utf-8")
    endpoint = (repo_root / "api/v1/endpoints/stocks.py").read_text(encoding="utf-8")
    auth = (repo_root / "api/middlewares/auth.py").read_text(encoding="utf-8")
    schema = (repo_root / "api/v1/schemas/basic_query.py").read_text(encoding="utf-8")
    frontend_api = (
        repo_root / "apps/dsa-web/src/api/stocks.ts"
    ).read_text(encoding="utf-8")
    component = (
        repo_root
        / "apps/dsa-web/src/components/research/StockResearchOverviewV142.tsx"
    ).read_text(encoding="utf-8")
    homepage = (
        repo_root / "apps/dsa-web/src/pages/HomePage.tsx"
    ).read_text(encoding="utf-8")
    styles = (repo_root / "apps/dsa-web/src/index.css").read_text(encoding="utf-8")

    yield _tokens(
        "v142_supported_market_symbol_mapping",
        service,
        (
            'return f"{match.group(1)}.SS"',
            'return f"{match.group(1)}.SZ"',
            'return f"{int(match.group(1)):04d}.HK"',
            'if code.endswith(".US"):',
            "normalize_crypto_symbol(code) is not None",
        ),
    )
    yield _tokens(
        "v142_observed_financial_trends",
        f"{service}\n{schema}",
        (
            '"financial_years": rows',
            '"revenue_growth"',
            '"net_income_growth"',
            '"operating_cash_flow"',
            '"observed_pe"',
            "PublicStockResearchOverviewResponse",
            "PublicStockFinancialYearPayload",
        ),
        forbidden=("fillna", "forward_fill", "or 0.0"),
    )
    yield _tokens(
        "v142_historical_valuation_method_and_boundary",
        service,
        (
            "fiscal_year_end_price_divided_by_diluted_eps",
            "Observed P/E uses fiscal-year-end price divided by annual diluted EPS",
            "不等同于实时、预测或目标估值",
            '"cache_status"] = "hit"',
        ),
        forbidden=(
            "target_price",
            "expected_return",
            "position_size",
            "stop_loss",
        ),
    )
    yield _tokens(
        "v142_anonymous_bounded_endpoint",
        f"{endpoint}\n{auth}",
        (
            '"/{stock_code}/research-overview"',
            "research-workflows|research-overview",
            "stock_research_overview",
            "platform_identity_from_request(request)",
            "_validate_and_normalize_stock_code(stock_code)",
            "_public_stock_research_overview_service.get_overview(normalized)",
            "does not invoke AI or public search",
        ),
        forbidden=("Depends(require_platform_user",),
    )
    yield _tokens(
        "v142_bilingual_tabbed_research_overview",
        component,
        (
            "Stock research overview",
            "个股研究总览",
            "Financial trends",
            "财务趋势",
            "Peer comparison",
            "同业对比",
            "News and events",
            "资讯事件",
            "K-line samples",
            "K线样本",
            "Sources and boundaries",
            "来源与边界",
            "stocksApi.researchOverview",
        ),
        forbidden=("Buy now", "Sell now", "Target price", "Guaranteed return"),
    )
    yield _tokens(
        "v142_condensed_homepage_preserves_details",
        f"{homepage}\n{component}\n{styles}",
        (
            "StockResearchOverviewV142",
            "v142DetailsExpanded",
            "v142-condensed",
            "展开全部详细模块",
            "收起详细模块",
            '[data-testid="basic-query-free-report"]',
        ),
    )
    yield _tokens(
        "v142_public_api_and_no_ai_boundary",
        f"{service}\n{frontend_api}\n{component}",
        (
            "/research-overview",
            "ai_used",
            "public_search_used",
            "Guest available",
            "游客可用",
            "No AI",
            "未用 AI",
            "not investment advice",
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
            "tests.test_public_stock_research_overview_v142",
        ],
        cwd=repo_root,
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v142_focused_backend", completed)


def focused_frontend_check(repo_root: Path) -> CheckResult:
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if npm is None:
        return CheckResult("v142_focused_frontend", False, {"reason": "npm_not_found"})
    completed = subprocess.run(
        [
            npm,
            "test",
            "--",
            "--run",
            "src/components/research/__tests__/StockResearchOverviewV142.test.tsx",
            "src/api/__tests__/stocks.test.ts",
            "src/pages/__tests__/HomePage.test.tsx",
        ],
        cwd=repo_root / "apps/dsa-web",
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return _process_result("v142_focused_frontend", completed)


def run_checks(repo_root: Path) -> Iterable[CheckResult]:
    yield from run_static_checks(repo_root)
    yield focused_backend_check(repo_root)
    yield focused_frontend_check(repo_root)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Verify DSA V142 stock research overview and peer comparison."
    )
    parser.add_argument("--repo-root", type=Path, default=REPO_ROOT)
    args = parser.parse_args()
    checks = list(run_checks(args.repo_root.resolve()))
    for check in checks:
        print(f"[{'OK' if check.ok else 'FAIL'}] {check.name}: {check.details}")
    if not all(check.ok for check in checks):
        return 1
    print("DSA_PLATFORM_STOCK_RESEARCH_OVERVIEW_V142_OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import json
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = (
    "DSA_PLATFORM_FREE_MARKET_STOCK_PREVIEW_V121_OK guest=true on_demand=true "
    "public_data=true ai_used=false bilingual=true mobile=true investment_advice=false"
)
REQUIRED_FILES = (
    "api/v1/endpoints/market_workspace.py",
    "apps/dsa-web/src/api/marketWorkspace.ts",
    "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx",
    "apps/dsa-web/src/components/market-home/PublicMarketStockPreviewV121.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
    "apps/dsa-web/src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx",
    "tests/test_market_workspace_v113.py",
    "tests/test_platform_free_market_stock_preview_v121_verifier.py",
    "docs/superpowers/plans/2026-07-14-dsa-v121-free-market-stock-preview.md",
)


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    details: dict = field(default_factory=dict)


def _source(root: Path, relative_path: str) -> str:
    path = root / relative_path
    return path.read_text(encoding="utf-8", errors="replace") if path.exists() else ""


def _check_files(root: Path) -> CheckResult:
    missing = [path for path in REQUIRED_FILES if not (root / path).exists()]
    return CheckResult("v121_required_files", "failed" if missing else "passed", {"missing": missing})


def _check_contract(root: Path) -> CheckResult:
    requirements = {
        "apps/dsa-web/src/api/marketWorkspace.ts": (
            "async getSymbol(symbol: string)",
            "/api/v1/market-workspace/symbol/",
        ),
        "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx": (
            "PublicMarketStockPreviewV121",
            "marketWorkspaceApi.getSymbol(item.symbol)",
            "查看 ${name} 数据详情",
            "View ${name} data preview",
            "onRetry={() => void loadPreview(previewItem)}",
            "clearPreview();",
        ),
        "apps/dsa-web/src/components/market-home/PublicMarketStockPreviewV121.tsx": (
            "public-market-stock-preview-v121",
            "公开数据预览",
            "Public data preview",
            "未使用 AI",
            "No AI used",
            "客观数据位置",
            "Objective data position",
            "不是方向预测",
            "not a forecast",
            "不构成投资建议",
            "No investment advice",
            "LineChart responsive",
        ),
        "apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx": (
            "not.toHaveBeenCalled()",
            "正在补充均线、历史曲线和公司资料",
            "公开数据暂时不可用",
            "重新加载数据详情",
            "进入完整查询",
        ),
        "apps/dsa-web/src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx": (
            "暂不可用",
            "No AI used",
            "Open full query",
            "近期收盘曲线",
        ),
    }
    missing: list[str] = []
    for path, tokens in requirements.items():
        text = _source(root, path)
        missing.extend(f"{path}:{token}" for token in tokens if token not in text)
    return CheckResult("v121_source_contract", "failed" if missing else "passed", {"missing": missing})


def _check_public_data_boundary(root: Path) -> CheckResult:
    home = _source(root, "apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx")
    preview = _source(root, "apps/dsa-web/src/components/market-home/PublicMarketStockPreviewV121.tsx")
    violations: list[str] = []
    allowed_call = "marketWorkspaceApi.getSymbol(item.symbol)"
    if home.count(allowed_call) != 1:
        violations.append(f"symbol-detail-call-count:{home.count(allowed_call)}")
    for token in ("analysisApi", "analyzeAsync", "SimpleModelPickerV112", "Kronos", "apiKey"):
        if token in home + preview:
            violations.append(f"ai-or-key-invocation:{token}")
    if re.search(r"\bsk-[A-Za-z0-9._-]{8,}\b", home + preview):
        violations.append("secret-like-key")
    for token in ("建议买入", "建议卖出", "目标价为", "仓位建议为", "预计收益"):
        if token in preview:
            violations.append(f"advice-language:{token}")
    return CheckResult("v121_public_data_no_ai_boundary", "failed" if violations else "passed", {"violations": violations})


def _run(check_id: str, cwd: Path, command: Sequence[str]) -> CheckResult:
    completed = subprocess.run(
        list(command), cwd=cwd, capture_output=True, text=True,
        encoding="utf-8", errors="replace", check=False,
    )
    return CheckResult(check_id, "passed" if completed.returncode == 0 else "failed", {
        "returncode": completed.returncode,
        "stdout_tail": completed.stdout[-1800:],
        "stderr_tail": completed.stderr[-1800:],
    })


def run_v121_checks(*, project_root: Path = REPO_ROOT, run_subprocess: bool = True) -> list[CheckResult]:
    root = project_root.resolve()
    results = [_check_files(root), _check_contract(root), _check_public_data_boundary(root)]
    if not run_subprocess:
        return results

    results.append(_run("v121_backend_tests", root, [
        sys.executable, "-m", "unittest",
        "tests.test_market_workspace_v113",
        "tests.test_platform_free_market_stock_preview_v121_verifier",
    ]))
    npm = shutil.which("npm.cmd") or shutil.which("npm") or "npm"
    frontend = root / "apps/dsa-web"
    results.append(_run("v121_frontend_tests", frontend, [
        npm, "test", "--", "--run",
        "src/api/__tests__/marketWorkspace.test.ts",
        "src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx",
        "src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx",
        "src/pages/__tests__/HomePage.test.tsx",
    ]))
    results.append(_run("v121_build", frontend, [npm, "run", "build"]))
    results.append(_run("v121_release_package", root, [sys.executable, "scripts/verify_platform_release_candidate_package.py"]))
    return results


def main() -> int:
    results = run_v121_checks()
    for result in results:
        print(f"[{'OK' if result.status == 'passed' else 'FAIL'}] {result.check_id}")
        print(f"  {json.dumps(result.details, ensure_ascii=False)}")
    if any(result.status == "failed" for result in results):
        print("DSA_PLATFORM_FREE_MARKET_STOCK_PREVIEW_V121_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

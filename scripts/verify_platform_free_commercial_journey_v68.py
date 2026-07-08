from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_OK"


@dataclass(frozen=True)
class CheckResult:
    check_id: str
    status: str
    elapsed_sec: float
    missing: list[str]

    def to_dict(self) -> dict:
        return {
            "check_id": self.check_id,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "missing": self.missing,
        }


REQUIRED_MARKERS: dict[str, list[str]] = {
    "apps/dsa-web/src/pages/HomePage.tsx": [
        "basicCommercialJourney",
        "basic-query-commercial-journey",
        "Free query journey",
        "免费查询完整路径",
        "Guest query works",
        "不登录也能查",
        "Free mode already shows the same visible research flow",
        "免费版已开放同样的研究流程",
        "quote, technicals, news, K-line, peers, risk",
        "行情、技术、资讯、K线、同业、风险",
        "Premium changes data sources",
        "高级版只换数据源",
        "Realtime news API",
        "实时新闻 API",
        "Filings / SEC API",
        "公告/SEC API",
        "Kronos / API model",
        "Kronos/API 模型",
        "not the page structure",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-commercial-journey",
        "免费查询完整路径",
        "免费版已开放",
        "先看结论",
        "再看研究",
        "最后决定是否深度分析",
        "行情、技术、资讯、K线、同业、风险",
        "高级版只换数据源",
        "实时新闻 API",
        "公告/SEC API",
        "Kronos/API 模型",
        "我的 API",
        "不登录也能查",
        "Upgrade to unlock",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_commercial_journey_v68.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v68-free-commercial-journey.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "free commercial journey",
        "same visible modules",
        "premium changes data source",
        "guest query works",
        "not investment advice",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V68 Free Commercial Journey Addendum",
        OK_MARKER,
        "scripts/verify_platform_free_commercial_journey_v68.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V68 Free Commercial Journey Manifest Addendum",
        OK_MARKER,
        "tests/test_platform_free_commercial_journey_v68.py",
    ],
}


def _read_text(root: Path, rel_path: str) -> str:
    return (root / rel_path).read_text(encoding="utf-8", errors="replace")


def _check_markers(root: Path, rel_path: str, markers: list[str]) -> CheckResult:
    started = time.monotonic()
    path = root / rel_path
    if not path.exists():
        return CheckResult(rel_path, "failed", time.monotonic() - started, ["file missing"])
    text = _read_text(root, rel_path)
    missing = [marker for marker in markers if marker not in text]
    return CheckResult(rel_path, "failed" if missing else "passed", time.monotonic() - started, missing)


def run_checks(root: Path = REPO_ROOT) -> list[CheckResult]:
    return [_check_markers(root, rel_path, markers) for rel_path, markers in REQUIRED_MARKERS.items()]


def main() -> int:
    results = run_checks(REPO_ROOT)
    failed = [result for result in results if result.status != "passed"]
    for result in results:
        prefix = "[OK]" if result.status == "passed" else "[FAIL]"
        print(f"{prefix} {result.check_id}")
        if result.missing:
            print(f"      missing={json.dumps(result.missing, ensure_ascii=False)}")
    print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
    if failed:
        print("DSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

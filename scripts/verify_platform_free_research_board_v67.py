from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK"


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
        "basicFreeResearchBoard",
        "basic-query-free-research-board",
        "basic-query-free-research-${card.key}",
        "key: 'news'",
        "key: 'kline'",
        "key: 'peer'",
        "key: 'risk'",
        "Free research board",
        "免费研究看板",
        "Research radar",
        "资讯雷达",
        "K-line read",
        "K线推演",
        "Peers / sector",
        "同业/板块",
        "Risk explanation",
        "风险解释",
        "同样内容，高级版换用 API 数据源",
        "not investment advice",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-free-research-board",
        "免费研究看板",
        "同样内容，高级版换用 API 数据源",
        "资讯雷达",
        "SEC 文件通道",
        "K线推演",
        "未来 5 根K线",
        "同业/板块",
        "QQQ",
        "XLK",
        "风险解释",
        "实时新闻",
        "不构成投资建议",
        "Research radar",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_research_board_v67.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v67-free-research-board.md": [
        OK_MARKER,
        "local-only",
        "No AI calls",
        "No public search",
        "free research board",
        "news radar",
        "K-line read",
        "peer and sector",
        "risk explanation",
        "not investment advice",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V67 Free Research Board Addendum",
        OK_MARKER,
        "scripts/verify_platform_free_research_board_v67.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V67 Free Research Board Manifest Addendum",
        OK_MARKER,
        "tests/test_platform_free_research_board_v67.py",
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
        print("DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

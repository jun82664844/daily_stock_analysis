from __future__ import annotations

import json
import time
from dataclasses import dataclass
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_FREE_BROKER_CONVERSION_V73_OK"


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
        "basicBrokerCockpit",
        "basic-query-broker-cockpit",
        "经纪人首屏研判",
        "现在值不值得继续看",
        "结论",
        "证据链",
        "风险边界",
        "升级后解决什么",
        "免费版先给完整研究结构",
        "高级版换实时 API、来源链接和模型深度",
        "不构成投资建议",
        "实时资讯和公告链接",
        "Kronos/API 模型深度",
    ],
    "apps/dsa-web/src/pages/__tests__/HomePage.test.tsx": [
        "basic-query-broker-cockpit",
        "经纪人首屏研判",
        "现在值不值得继续看",
        "升级后解决什么",
        "brokerCockpit.compareDocumentPosition(commercialJourney)",
        "primarySummary.compareDocumentPosition(brokerCockpit)",
    ],
    ".gitignore": [
        "!scripts/verify_platform_free_broker_conversion_v73.py",
    ],
    "docs/superpowers/plans/2026-07-08-dsa-v73-free-broker-conversion.md": [
        "DSA V73 Free Broker Conversion Implementation Plan",
        "broker-style decision cockpit",
        "basic-query-broker-cockpit",
        "not investment advice",
    ],
    "docs/superpowers/platform-review-slices.md": [
        "V73 Free Broker Conversion Addendum",
        OK_MARKER,
        "scripts/verify_platform_free_broker_conversion_v73.py",
    ],
    "docs/superpowers/platform-release-candidate-manifest.md": [
        "V73 Free Broker Conversion Manifest Addendum",
        OK_MARKER,
        "tests/test_platform_free_broker_conversion_v73.py",
    ],
    "docs/superpowers/platform-local-v1-acceptance-status.md": [
        "V73 Free Broker Conversion Acceptance",
        OK_MARKER,
        "经纪人首屏研判",
        "basic-query-broker-cockpit",
    ],
    "scripts/verify_platform_release_candidate_package.py": [
        "verify_platform_free_broker_conversion_v73.py",
        "2026-07-08-dsa-v73-free-broker-conversion.md",
    ],
    "tests/test_platform_release_candidate_package.py": [
        "include_v73",
        "test_reports_missing_free_broker_conversion_v73_files",
        "verify_platform_free_broker_conversion_v73.py",
        "2026-07-08-dsa-v73-free-broker-conversion.md",
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
        print("DSA_PLATFORM_FREE_BROKER_CONVERSION_V73_FAILED")
        return 1
    print(OK_MARKER)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

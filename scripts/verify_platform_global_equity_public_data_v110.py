from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Sequence


REPO_ROOT = Path(__file__).resolve().parents[1]
OK_MARKER = "DSA_PLATFORM_GLOBAL_EQUITY_PUBLIC_DATA_V110_OK"
REQUIRED_FILES = (
    "src/services/global_equity_enrichment_service.py",
    "tests/test_global_equity_enrichment_service_v110.py",
    "tests/test_basic_query_global_equity_v110.py",
    "apps/dsa-web/src/components/research/GlobalEquityEnrichmentCard.tsx",
    "apps/dsa-web/src/components/research/__tests__/GlobalEquityEnrichmentCard.test.tsx",
    "docs/superpowers/plans/2026-07-12-dsa-v110-global-equity-public-data.md",
)
MARKERS = (
    "global_equity_public_adapter",
    "sec_edgar_submissions",
    "hkexnews_official_search",
    "yahoo_finance_search_feed",
    "GLOBAL_EQUITY_ENRICHMENT_ENABLED",
    "Information and data only",
)


def static_checks(root: Path) -> dict:
    missing_files = [item for item in REQUIRED_FILES if not (root / item).exists()]
    combined = "\n".join(
        (root / item).read_text(encoding="utf-8", errors="replace")
        for item in REQUIRED_FILES
        if (root / item).exists()
    )
    combined += "\n" + (root / ".env.example").read_text(encoding="utf-8", errors="replace")
    missing_markers = [item for item in MARKERS if item.lower() not in combined.lower()]
    return {
        "passed": not missing_files and not missing_markers,
        "missing_files": missing_files,
        "missing_markers": missing_markers,
    }


def live_checks(base_url: str) -> dict:
    results = {}
    for symbol, market in (("AAPL", "us"), ("0700.HK", "hk")):
        encoded = urllib.parse.quote(symbol, safe="")
        url = f"{base_url.rstrip('/')}/api/v1/stocks/{encoded}/snapshot"
        try:
            with urllib.request.urlopen(url, timeout=30) as response:
                payload = json.loads(response.read().decode("utf-8"))
            enrichment = ((payload.get("intelligence") or {}).get("global_equity_enrichment") or {})
            channels = {item.get("category"): item for item in enrichment.get("channels") or []}
            news = channels.get("news") or {}
            filings = channels.get("filings") or {}
            fundamentals = channels.get("fundamentals") or {}
            passed = (
                payload.get("market") == market
                and enrichment.get("source") == "global_equity_public_adapter"
                and enrichment.get("ai_used") is False
                and enrichment.get("public_search_used") is False
                and news.get("status") == "available"
                and len(news.get("items") or []) >= 1
                and fundamentals.get("status") == "available"
            )
            if market == "us":
                passed = passed and filings.get("status") == "available" and all(
                    str(item.get("url") or "").startswith("https://www.sec.gov/")
                    for item in filings.get("items") or []
                ) and len(filings.get("items") or []) >= 1
            else:
                passed = passed and filings.get("source") == "hkexnews_official_search"
                passed = passed and str(filings.get("official_url") or "").startswith("https://www1.hkexnews.hk/")
            results[symbol] = {
                "passed": bool(passed),
                "status": enrichment.get("status"),
                "news_items": len(news.get("items") or []),
                "filing_items": len(filings.get("items") or []),
                "cache_hit": (enrichment.get("diagnostics") or {}).get("cache_hit"),
            }
        except Exception as exc:
            results[symbol] = {"passed": False, "error": type(exc).__name__}
    return {"passed": all(item["passed"] for item in results.values()), "symbols": results}


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--python-exe", default=sys.executable)
    parser.add_argument("--live-url")
    parser.add_argument("--skip-tests", action="store_true")
    args = parser.parse_args(argv)
    checks = {"static": static_checks(REPO_ROOT)}
    if not args.skip_tests:
        completed = subprocess.run(
            [
                args.python_exe,
                "-m",
                "unittest",
                "tests.test_global_equity_enrichment_service_v110",
                "tests.test_basic_query_global_equity_v110",
            ],
            cwd=REPO_ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
            env={**os.environ, "GLOBAL_EQUITY_ENRICHMENT_ENABLED": "false"},
        )
        checks["tests"] = {
            "passed": completed.returncode == 0,
            "output_tail": (completed.stdout + completed.stderr)[-1600:],
        }
    if args.live_url:
        checks["live"] = live_checks(args.live_url)
    print(json.dumps(checks, ensure_ascii=False, indent=2))
    passed = all(item["passed"] for item in checks.values())
    if passed:
        print(OK_MARKER)
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import time
import urllib.request
from http.cookiejar import CookieJar
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence
from urllib.error import HTTPError


REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from scripts.verify_platform_local_functional_v5 import (
    DEFAULT_BASE_URL,
    _get_json,
    _json_request,
    _new_smoke_credentials,
    _open_json,
    _url_join,
    run_local_functional_v5_checks,
)


OK_MARKER = "DSA_PLATFORM_LOCAL_USABILITY_V6_OK"

REQUIRED_FILES = (
    "docs/superpowers/platform-local-v1-acceptance-status.md",
    "docs/superpowers/platform-review-slices.md",
    "docs/superpowers/platform-release-candidate-manifest.md",
    "docs/superpowers/platform-product-rules.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md",
    "scripts/verify_platform_local_functional_v5.py",
    "scripts/verify_platform_local_usability_v6.py",
    "scripts/verify_local_v1_operability.py",
    "scripts/verify_platform_query_quality_v4.py",
    "scripts/verify_platform_user_e2e.py",
    "scripts/verify_platform_billing_lifecycle.py",
    "scripts/verify_platform_release_candidate_package.py",
    "tests/test_platform_local_functional_v5.py",
    "tests/test_platform_local_usability_v6.py",
    "tests/test_platform_query_quality_v4.py",
    "tests/test_platform_user_journey.py",
    "tests/test_billing_sandbox_flow.py",
    "tests/test_billing_subscription_lifecycle.py",
    "apps/dsa-web/src/api/stocks.ts",
    "apps/dsa-web/src/api/platform.ts",
    "apps/dsa-web/src/pages/HomePage.tsx",
    "apps/dsa-web/src/pages/AccountPage.tsx",
    "apps/dsa-web/src/pages/AdminPage.tsx",
    "apps/dsa-web/src/components/layout/SidebarNav.tsx",
)

VERIFIER_FILES = (
    "scripts/verify_local_v1_operability.py",
    "scripts/verify_platform_query_quality_v4.py",
    "scripts/verify_platform_user_e2e.py",
    "scripts/verify_platform_billing_lifecycle.py",
    "scripts/verify_platform_release_candidate_package.py",
    "scripts/verify_platform_local_functional_v5.py",
    "scripts/verify_platform_local_usability_v6.py",
)

DOC_FILES = (
    "docs/superpowers/platform-local-v1-acceptance-status.md",
    "docs/superpowers/platform-review-slices.md",
    "docs/superpowers/platform-release-candidate-manifest.md",
    "docs/superpowers/platform-product-rules.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md",
    "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md",
)

MARKET_SNAPSHOT_EXPECTATIONS = {
    "600519": {"market": "cn", "lane": "a_share_market_data"},
    "AAPL": {"market": "us", "lane": "us_market_data"},
    "HK00700": {"market": "hk", "lane": "hk_market_data"},
    "BTC-USD": {"market": "crypto", "lane": "crypto_market_data"},
}


@dataclass(frozen=True)
class UsabilityV6Result:
    check_id: str
    title: str
    status: str
    elapsed_sec: float = 0.0
    error: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)
    optional: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "check_id": self.check_id,
            "title": self.title,
            "status": self.status,
            "elapsed_sec": round(self.elapsed_sec, 3),
            "error": self.error,
            "metadata": self.metadata,
            "optional": self.optional,
        }


def _result(
    check_id: str,
    title: str,
    started: float,
    *,
    status: str = "passed",
    error: str = "",
    metadata: dict[str, Any] | None = None,
    optional: bool = False,
) -> UsabilityV6Result:
    return UsabilityV6Result(
        check_id=check_id,
        title=title,
        status=status,
        elapsed_sec=time.monotonic() - started,
        error=error,
        metadata=metadata or {},
        optional=optional,
    )


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _status_of(item: Any) -> str:
    return str(getattr(item, "status", "failed"))


def _check_id_of(item: Any) -> str:
    return str(getattr(item, "check_id", "unknown"))


def _is_optional(item: Any) -> bool:
    return bool(getattr(item, "optional", False))


def _run_required_files_check(root: Path) -> UsabilityV6Result:
    started = time.monotonic()
    missing = sorted(rel_path for rel_path in REQUIRED_FILES if not (root / rel_path).exists())
    if missing:
        return _result(
            "required_files_present",
            "Local Usability V6 required files exist",
            started,
            status="failed",
            error="required files are missing",
            metadata={"missing_files": missing},
        )
    return _result(
        "required_files_present",
        "Local Usability V6 required files exist",
        started,
        metadata={"checked_files": sorted(REQUIRED_FILES)},
    )


def _run_verifiers_visible_check(root: Path) -> UsabilityV6Result:
    started = time.monotonic()
    ignored: list[str] = []
    for rel_path in VERIFIER_FILES:
        completed = subprocess.run(
            ["git", "check-ignore", "-q", rel_path],
            cwd=root,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            check=False,
        )
        if completed.returncode == 0:
            ignored.append(rel_path)
    if ignored:
        return _result(
            "verifiers_visible_to_git",
            "Critical local verifier files are not gitignored",
            started,
            status="failed",
            error="verifier files are hidden by gitignore",
            metadata={"ignored_files": ignored},
        )
    return _result(
        "verifiers_visible_to_git",
        "Critical local verifier files are not gitignored",
        started,
        metadata={"checked_files": sorted(VERIFIER_FILES)},
    )


def _run_docs_safety_check(root: Path) -> UsabilityV6Result:
    started = time.monotonic()
    missing_docs = [rel_path for rel_path in DOC_FILES if not (root / rel_path).exists()]
    combined = "\n".join(_read_text(root / rel_path) for rel_path in DOC_FILES if (root / rel_path).exists())
    lower = combined.lower()
    requirements = {
        "DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK": "DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK" in combined,
        OK_MARKER: OK_MARKER in combined,
        "No-go": "no-go" in lower or "不可上线" in combined,
        "sandbox": "sandbox" in lower,
        "not real payment": "not real payment" in lower or "不代表真实支付" in combined,
        "not investment advice": "not investment advice" in lower or "不构成投资建议" in combined,
        "Do not commit real API Key": "do not commit real api key" in lower or "不得提交真实 api key" in lower,
    }
    missing_requirements = sorted(label for label, present in requirements.items() if not present)
    if missing_docs or missing_requirements:
        return _result(
            "docs_keep_v6_safety_copy",
            "Docs keep V6 marker and local-only safety copy",
            started,
            status="failed",
            error="V6 docs are missing required safety copy",
            metadata={"missing_docs": missing_docs, "missing_requirements": missing_requirements},
        )
    return _result(
        "docs_keep_v6_safety_copy",
        "Docs keep V6 marker and local-only safety copy",
        started,
        metadata={"checked_docs": list(DOC_FILES), "requirements": sorted(requirements)},
    )


def _run_v5_required_live_gate(v5_results: Sequence[Any]) -> UsabilityV6Result:
    started = time.monotonic()
    required_bad = [
        _check_id_of(result)
        for result in v5_results
        if not _is_optional(result) and _status_of(result) != "passed"
    ]
    if required_bad:
        return _result(
            "v5_required_live_gate",
            "V5 required local checks have no failures or degraded live account state",
            started,
            status="failed",
            error="required V5 checks are not fully passed",
            metadata={"bad_required_checks": required_bad},
        )
    return _result(
        "v5_required_live_gate",
        "V5 required local checks have no failures or degraded live account state",
        started,
        metadata={"checked_results": len(v5_results)},
    )


def _run_v5_optional_degradation_check(v5_results: Sequence[Any]) -> UsabilityV6Result:
    started = time.monotonic()
    degraded = [
        _check_id_of(result)
        for result in v5_results
        if _is_optional(result) and _status_of(result) != "passed"
    ]
    if degraded:
        return _result(
            "v5_optional_live_degradation",
            "Optional live market data degradation is recorded but does not block V6",
            started,
            status="degraded",
            error="optional live checks degraded",
            metadata={"degraded_optional_checks": degraded},
            optional=True,
        )
    return _result(
        "v5_optional_live_degradation",
        "Optional live market data degradation is recorded but does not block V6",
        started,
        metadata={"degraded_optional_checks": []},
        optional=True,
    )


def evaluate_market_snapshot_results(results: dict[str, dict[str, Any]]) -> list[str]:
    bad_symbols: list[str] = []
    for symbol, expected in MARKET_SNAPSHOT_EXPECTATIONS.items():
        item = results.get(symbol)
        if not item or item.get("error"):
            bad_symbols.append(symbol)
            continue
        if item.get("status_code") != 200:
            bad_symbols.append(symbol)
            continue
        if item.get("ai_used") is not False:
            bad_symbols.append(symbol)
            continue
        if item.get("market") != expected["market"] or item.get("lane") != expected["lane"]:
            bad_symbols.append(symbol)
    return bad_symbols


def _run_optional_live_multi_market_snapshot_check(base_url: str) -> UsabilityV6Result:
    started = time.monotonic()
    email, password = _new_smoke_credentials("local-v6-market")
    opener = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(CookieJar()))
    snapshots: dict[str, dict[str, Any]] = {}
    metadata: dict[str, Any] = {"smoke_email": email, "cleanup_prefix": "e2e+", "snapshots": snapshots}
    try:
        register_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/register"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["register_status_code"] = register_status
        if register_status >= 400:
            return _result(
                "optional_live_multi_market_snapshot",
                "Optional live no-AI snapshot smoke across CN/US/HK/crypto",
                started,
                status="degraded",
                error="platform smoke user registration failed",
                metadata=metadata,
                optional=True,
            )
        login_status, _ = _open_json(
            opener,
            _json_request(_url_join(base_url, "/api/v1/platform/login"), {"email": email, "password": password}),
            timeout=15,
        )
        metadata["login_status_code"] = login_status
        if login_status >= 400:
            return _result(
                "optional_live_multi_market_snapshot",
                "Optional live no-AI snapshot smoke across CN/US/HK/crypto",
                started,
                status="degraded",
                error="platform smoke user login failed",
                metadata=metadata,
                optional=True,
            )
        for symbol in MARKET_SNAPSHOT_EXPECTATIONS:
            try:
                status_code, payload = _get_json(opener, _url_join(base_url, f"/api/v1/stocks/{symbol}/snapshot"), timeout=20)
                route = payload.get("route", {}) if isinstance(payload, dict) else {}
                degradation = payload.get("degradation", {}) if isinstance(payload, dict) else {}
                snapshots[symbol] = {
                    "status_code": status_code,
                    "market": payload.get("market") if isinstance(payload, dict) else None,
                    "ai_used": payload.get("ai_used") if isinstance(payload, dict) else None,
                    "lane": route.get("data_source_lane") if isinstance(route, dict) else None,
                    "degradation": degradation if isinstance(degradation, dict) else None,
                }
            except HTTPError as exc:
                snapshots[symbol] = {"status_code": exc.code, "error": f"HTTP {exc.code}: {exc.reason}"}
            except Exception as exc:
                snapshots[symbol] = {"error": str(exc)}
    except Exception as exc:
        return _result(
            "optional_live_multi_market_snapshot",
            "Optional live no-AI snapshot smoke across CN/US/HK/crypto",
            started,
            status="degraded",
            error=str(exc),
            metadata=metadata,
            optional=True,
        )

    bad_symbols = evaluate_market_snapshot_results(snapshots)
    if bad_symbols:
        return _result(
            "optional_live_multi_market_snapshot",
            "Optional live no-AI snapshot smoke across CN/US/HK/crypto",
            started,
            status="degraded",
            error="one or more live market snapshots were unavailable, slow, or not routed as no-AI",
            metadata={**metadata, "bad_symbols": bad_symbols},
            optional=True,
        )
    return _result(
        "optional_live_multi_market_snapshot",
        "Optional live no-AI snapshot smoke across CN/US/HK/crypto",
        started,
        metadata=metadata,
        optional=True,
    )


def _load_v5_results(
    *,
    root: Path,
    python_exe: str,
    base_url: str,
    run_subprocess: bool,
    run_live: bool,
) -> list[Any]:
    return list(
        run_local_functional_v5_checks(
            project_root=root,
            python_exe=python_exe,
            base_url=base_url,
            run_subprocess=run_subprocess,
            run_live=run_live,
            include_optional_live=True,
        )
    )


def run_local_usability_v6_checks(
    *,
    project_root: str | Path | None = None,
    python_exe: str | None = None,
    base_url: str = DEFAULT_BASE_URL,
    run_subprocess: bool = True,
    run_live: bool = True,
    v5_results: Sequence[Any] | None = None,
    include_v6_market_smoke: bool = True,
) -> list[UsabilityV6Result]:
    root = Path(project_root).resolve() if project_root is not None else REPO_ROOT
    py = python_exe or sys.executable
    results = [
        _run_required_files_check(root),
        _run_verifiers_visible_check(root),
        _run_docs_safety_check(root),
    ]
    loaded_v5_results = list(v5_results) if v5_results is not None else _load_v5_results(
        root=root,
        python_exe=py,
        base_url=base_url,
        run_subprocess=run_subprocess,
        run_live=run_live,
    )
    results.append(_run_v5_required_live_gate(loaded_v5_results))
    results.append(_run_v5_optional_degradation_check(loaded_v5_results))
    if run_live and include_v6_market_smoke:
        results.append(_run_optional_live_multi_market_snapshot_check(base_url))
    return results


def _passed_for_marker(results: Sequence[UsabilityV6Result]) -> bool:
    return all(result.status != "failed" for result in results)


def _print_text_report(results: Sequence[UsabilityV6Result]) -> None:
    for result in results:
        if result.status == "passed":
            marker = "[OK]"
        elif result.status in {"degraded", "skipped", "planned"}:
            marker = "[--]"
        else:
            marker = "[FAIL]"
        print(f"{marker} {result.check_id}: {result.title}")
        if result.error:
            print(f"  error: {result.error}")
        if result.metadata:
            print(f"  metadata: {json.dumps(result.metadata, ensure_ascii=False)}")
    if _passed_for_marker(results):
        print(OK_MARKER)


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify DSA platform Local Usability V6 closure")
    parser.add_argument("--project-root", default=str(REPO_ROOT), help="DSA project root")
    parser.add_argument("--python", dest="python_exe", default=sys.executable, help="Python executable for subprocess checks")
    parser.add_argument("--base-url", default=DEFAULT_BASE_URL, help="Local running WebUI base URL")
    parser.add_argument("--skip-subprocess", action="store_true", help="Skip V5 unittest and existing verifier subprocess checks")
    parser.add_argument("--skip-live", action="store_true", help="Skip live 8018 HTTP checks")
    parser.add_argument("--skip-v6-market-smoke", action="store_true", help="Skip optional V6 multi-market live snapshot smoke")
    parser.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    args = parser.parse_args(argv)

    results = run_local_usability_v6_checks(
        project_root=args.project_root,
        python_exe=args.python_exe,
        base_url=args.base_url,
        run_subprocess=not args.skip_subprocess,
        run_live=not args.skip_live,
        include_v6_market_smoke=not args.skip_v6_market_smoke,
    )
    if args.json:
        print(json.dumps([result.to_dict() for result in results], ensure_ascii=False, indent=2))
        if _passed_for_marker(results):
            print(OK_MARKER)
    else:
        _print_text_report(results)
    return 0 if _passed_for_marker(results) else 1


if __name__ == "__main__":
    raise SystemExit(main())

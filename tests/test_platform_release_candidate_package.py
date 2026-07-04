import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch


SAFE_ENV = """\
ADMIN_AUTH_ENABLED=true
PLATFORM_USER_AUTH_ENABLED=true
PLATFORM_CSRF_ENABLED=true
DATABASE_PATH=/var/lib/dsa/stock_analysis.db
DSA_SECRET_SOURCE=managed-secret-store-or-protected-env
LITELLM_MODEL=deepseek/deepseek-v4-flash
SEARXNG_PUBLIC_INSTANCES_ENABLED=false
ENABLE_FUNDAMENTAL_PIPELINE=false
ENABLE_CHIP_DISTRIBUTION=false
DAILY_MARKET_CONTEXT_ENABLED=false
REALTIME_CACHE_TTL=600
BILLING_ENABLED=false
DEBUG=false
CORS_ALLOW_ALL=false
LOCAL_LLM_ENABLED=false
LOCAL_LLM_MAX_CONCURRENT=2
"""


class PlatformReleaseCandidatePackageVerifierTestCase(unittest.TestCase):
    def _write_file(self, root: Path, rel_path: str, content: str = "ok\n") -> None:
        path = root / rel_path
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")

    def _write_minimal_package(
        self,
        root: Path,
        *,
        include_manifest: bool = True,
        include_v6: bool = True,
        include_v7: bool = True,
        include_v8: bool = True,
        include_v9: bool = True,
        include_v10: bool = True,
        include_v11: bool = True,
        include_v12: bool = True,
        include_v13: bool = True,
        include_v14: bool = True,
        include_v15: bool = True,
        include_v16: bool = True,
        include_v17: bool = True,
        include_v18: bool = True,
        include_v19: bool = True,
        include_v20: bool = True,
        include_v21: bool = True,
        include_v22: bool = True,
        include_v23: bool = True,
        include_v24: bool = True,
        include_v25: bool = True,
        include_v26: bool = True,
        include_v27: bool = True,
        include_v28: bool = True,
        include_v29: bool = True,
        include_v30: bool = True,
        env_text: str = SAFE_ENV,
    ) -> None:
        required_docs = {
            "docs/superpowers/platform-local-v1-acceptance-status.md": "not investment advice\n",
            "docs/superpowers/platform-local-v1-operability.md": "operability\n",
            "docs/superpowers/platform-local-v1-security-checklist.md": "security\n",
            "docs/superpowers/platform-product-rules.md": "product\n",
            "docs/superpowers/platform-v2-launch-readiness.md": (
                "No-go\nreal payment disabled\nnot investment advice\n"
                "Do not commit real API Key\n"
            ),
            "docs/superpowers/platform-v2-handoff-status.md": "modified\nuntracked\n",
            "docs/superpowers/platform-legal-copy-draft.md": (
                "not investment advice\nprivacy\nAPI Key custody\n"
            ),
            "docs/superpowers/platform-production-env.example": env_text,
            "docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_USABILITY_V6_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v7-query-speed.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v9-market-source-health.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_MARKET_SOURCE_HEALTH_V9_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v10-persistent-market-cache.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_PERSISTENT_MARKET_CACHE_V10_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v11-market-source-ops.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK\n"
            ),
            "docs/superpowers/plans/2026-07-02-dsa-local-v12-market-prewarm-console.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v14-real-use-loop.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v15-user-query-loop.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v16-browser-user-loop.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v17-user-watchlist.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_WATCHLIST_V17_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v18-watchlist-board.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v19-query-workspace.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md": (
                "No-go\nsandbox\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_PUBLIC_USER_FLOW_V21_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDSA_PLATFORM_LOCAL_MARKET_REFRESH_V22_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\n"
                "Historical AI report\ncurrent quote\nsnapshot?refresh=true\nno-AI\n"
                "DSA_PLATFORM_LOCAL_HISTORY_SNAPSHOT_BOUNDARY_V23_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "History Center\nmarket/code/report type/time/refresh\nsession-only\n"
                "current quote\nno-AI\nDSA_PLATFORM_LOCAL_HISTORY_CENTER_V24_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "History Center\nbackend filtering\npersistent refresh marker\n"
                "current quote\nno-AI\ndoes not rewrite old AI reports\n"
                "DSA_PLATFORM_LOCAL_HISTORY_CENTER_V25_OK\n"
            ),
            "docs/superpowers/plans/2026-07-03-dsa-local-v26-history-center-usability.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "History Center\nlocalStorage\nvalidated\nbackend total\n"
                "DSA_PLATFORM_LOCAL_HISTORY_CENTER_V26_OK\n"
            ),
            "docs/superpowers/plans/2026-07-04-dsa-local-v27-history-export.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "History Center\nexport\nMarkdown\nJSON\nsecret redact\n"
                "AI used: false\nDSA_PLATFORM_LOCAL_HISTORY_EXPORT_V27_OK\n"
            ),
            "docs/superpowers/plans/2026-07-04-dsa-local-v28-history-state.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "History Center\nanalysis_history_user_states\nowner-scoped\n"
                "favorite\nimportant\narchived\nread\nnote\n"
                "AI used: false\nDSA_PLATFORM_LOCAL_HISTORY_STATE_V28_OK\n"
            ),
            "docs/superpowers/plans/2026-07-04-dsa-local-v29-history-ops.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "History Center\nnote_search\nowner-scoped\nactive default\n"
                "date group\nbatch important\nbatch read\nno-AI\n"
                "DSA_PLATFORM_LOCAL_HISTORY_OPS_V29_OK\n"
            ),
            "docs/superpowers/plans/2026-07-04-dsa-local-v30-history-detail.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nDo not delete history reports\n"
                "report detail search\nsection jumps\nsame-stock timeline\n"
                "owner-scoped\nexisting history list\nno-AI\n"
                "DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK\n"
            ),
            "docs/superpowers/platform-review-slices.md": (
                "backend-platform-foundation\n"
                "tests-and-verifiers\n"
                "`api/middlewares/auth.py`\n"
            ),
        }
        if include_manifest:
            required_docs["docs/superpowers/platform-release-candidate-manifest.md"] = (
                "backend-platform-foundation\n"
                "tests-and-verifiers\n"
                "recommended commit order\n"
                "`api/middlewares/auth.py`\n"
            )
        for rel_path, content in required_docs.items():
            self._write_file(root, rel_path, content)
        for rel_path in (
            "scripts/verify_local_v1_operability.py",
            "scripts/verify_platform_v2_readiness.py",
            "scripts/verify_platform_release_candidate_package.py",
            "scripts/verify_platform_user_e2e.py",
            "scripts/verify_platform_billing_lifecycle.py",
            "scripts/verify_platform_query_quality_v4.py",
            "scripts/verify_platform_local_functional_v5.py",
            "scripts/verify_platform_local_usability_v6.py",
            "scripts/verify_platform_local_query_speed_v7.py",
            "scripts/verify_platform_local_query_resilience_v8.py",
            "scripts/verify_platform_local_market_source_health_v9.py",
            "scripts/verify_platform_local_persistent_market_cache_v10.py",
            "scripts/verify_platform_local_market_source_ops_v11.py",
            "scripts/verify_platform_local_market_prewarm_console_v12.py",
            "scripts/verify_platform_local_market_recovery_console_v13.py",
            "scripts/verify_platform_local_real_use_loop_v14.py",
            "scripts/verify_platform_local_user_query_loop_v15.py",
            "scripts/verify_platform_local_browser_user_loop_v16.py",
            "scripts/verify_platform_local_watchlist_v17.py",
            "scripts/verify_platform_local_watchlist_board_v18.py",
            "scripts/verify_platform_local_query_workspace_v19.py",
            "scripts/verify_platform_local_public_entry_v20.py",
            "scripts/verify_platform_local_public_user_flow_v21.py",
            "scripts/verify_platform_local_market_refresh_v22.py",
            "scripts/verify_platform_local_history_snapshot_boundary_v23.py",
            "scripts/verify_platform_local_history_center_v24.py",
            "scripts/verify_platform_local_history_center_v25.py",
            "scripts/verify_platform_local_history_center_v26.py",
            "scripts/verify_platform_local_history_export_v27.py",
            "scripts/verify_platform_local_history_state_v28.py",
            "scripts/verify_platform_local_history_ops_v29.py",
            "scripts/verify_platform_local_history_detail_v30.py",
            "scripts/cleanup_platform_e2e_data.py",
            "src/platform_watchlist.py",
            "src/services/market_source_ops.py",
            "src/services/local_functional_status.py",
            "tests/test_platform_release_candidate_package.py",
            "tests/test_platform_user_e2e_safety.py",
            "tests/test_billing_subscription_lifecycle.py",
            "tests/test_platform_query_quality_v4.py",
            "tests/test_platform_local_functional_v5.py",
            "tests/test_platform_local_usability_v6.py",
            "tests/test_platform_local_query_speed_v7.py",
            "tests/test_platform_local_query_resilience_v8.py",
            "tests/test_platform_local_market_source_health_v9.py",
            "tests/test_platform_local_persistent_market_cache_v10.py",
            "tests/test_platform_local_market_source_ops_v11.py",
            "tests/test_platform_local_market_prewarm_console_v12.py",
            "tests/test_platform_local_market_recovery_console_v13.py",
            "tests/test_platform_local_real_use_loop_v14.py",
            "tests/test_platform_local_user_query_loop_v15.py",
            "tests/test_platform_local_browser_user_loop_v16.py",
            "tests/test_platform_local_watchlist_v17.py",
            "tests/test_platform_local_watchlist_v17_verifier.py",
            "tests/test_platform_local_watchlist_board_v18.py",
            "tests/test_platform_local_query_workspace_v19.py",
            "tests/test_platform_local_public_entry_v20.py",
            "tests/test_platform_local_public_user_flow_v21.py",
            "tests/test_platform_local_market_refresh_v22.py",
            "tests/test_platform_local_history_snapshot_boundary_v23.py",
            "tests/test_platform_local_history_center_v24.py",
            "tests/test_platform_local_history_center_v25.py",
            "tests/test_platform_local_history_center_v26.py",
            "tests/test_platform_local_history_export_v27.py",
            "tests/test_platform_local_history_state_v28.py",
            "tests/test_platform_local_history_ops_v29.py",
            "tests/test_platform_local_history_detail_v30.py",
            "apps/dsa-web/playwright.config.ts",
            "apps/dsa-web/e2e/platform-user-e2e.spec.ts",
        ):
            if not include_v6 and rel_path in {
                "scripts/verify_platform_local_usability_v6.py",
                "tests/test_platform_local_usability_v6.py",
            }:
                continue
            if not include_v7 and rel_path in {
                "scripts/verify_platform_local_query_speed_v7.py",
                "tests/test_platform_local_query_speed_v7.py",
            }:
                continue
            if not include_v8 and rel_path in {
                "scripts/verify_platform_local_query_resilience_v8.py",
                "tests/test_platform_local_query_resilience_v8.py",
            }:
                continue
            if not include_v9 and rel_path in {
                "scripts/verify_platform_local_market_source_health_v9.py",
                "tests/test_platform_local_market_source_health_v9.py",
            }:
                continue
            if not include_v10 and rel_path in {
                "scripts/verify_platform_local_persistent_market_cache_v10.py",
                "tests/test_platform_local_persistent_market_cache_v10.py",
            }:
                continue
            if not include_v11 and rel_path in {
                "scripts/verify_platform_local_market_source_ops_v11.py",
                "src/services/market_source_ops.py",
                "tests/test_platform_local_market_source_ops_v11.py",
            }:
                continue
            if not include_v12 and rel_path in {
                "scripts/verify_platform_local_market_prewarm_console_v12.py",
                "tests/test_platform_local_market_prewarm_console_v12.py",
            }:
                continue
            if not include_v13 and rel_path in {
                "scripts/verify_platform_local_market_recovery_console_v13.py",
                "tests/test_platform_local_market_recovery_console_v13.py",
            }:
                continue
            if not include_v14 and rel_path in {
                "scripts/verify_platform_local_real_use_loop_v14.py",
                "src/services/local_functional_status.py",
                "tests/test_platform_local_real_use_loop_v14.py",
            }:
                continue
            if not include_v15 and rel_path in {
                "scripts/verify_platform_local_user_query_loop_v15.py",
                "tests/test_platform_local_user_query_loop_v15.py",
            }:
                continue
            if not include_v16 and rel_path in {
                "scripts/verify_platform_local_browser_user_loop_v16.py",
                "tests/test_platform_local_browser_user_loop_v16.py",
            }:
                continue
            if not include_v17 and rel_path in {
                "scripts/verify_platform_local_watchlist_v17.py",
                "src/platform_watchlist.py",
                "tests/test_platform_local_watchlist_v17.py",
                "tests/test_platform_local_watchlist_v17_verifier.py",
            }:
                continue
            if not include_v18 and rel_path in {
                "scripts/verify_platform_local_watchlist_board_v18.py",
                "tests/test_platform_local_watchlist_board_v18.py",
            }:
                continue
            if not include_v19 and rel_path in {
                "scripts/verify_platform_local_query_workspace_v19.py",
                "tests/test_platform_local_query_workspace_v19.py",
            }:
                continue
            if not include_v20 and rel_path in {
                "scripts/verify_platform_local_public_entry_v20.py",
                "tests/test_platform_local_public_entry_v20.py",
            }:
                continue
            if not include_v21 and rel_path in {
                "scripts/verify_platform_local_public_user_flow_v21.py",
                "tests/test_platform_local_public_user_flow_v21.py",
            }:
                continue
            if not include_v22 and rel_path in {
                "scripts/verify_platform_local_market_refresh_v22.py",
                "tests/test_platform_local_market_refresh_v22.py",
            }:
                continue
            if not include_v23 and rel_path in {
                "scripts/verify_platform_local_history_snapshot_boundary_v23.py",
                "tests/test_platform_local_history_snapshot_boundary_v23.py",
            }:
                continue
            if not include_v24 and rel_path in {
                "scripts/verify_platform_local_history_center_v24.py",
                "tests/test_platform_local_history_center_v24.py",
            }:
                continue
            if not include_v25 and rel_path in {
                "scripts/verify_platform_local_history_center_v25.py",
                "tests/test_platform_local_history_center_v25.py",
            }:
                continue
            if not include_v26 and rel_path in {
                "scripts/verify_platform_local_history_center_v26.py",
                "tests/test_platform_local_history_center_v26.py",
            }:
                continue
            if not include_v27 and rel_path in {
                "scripts/verify_platform_local_history_export_v27.py",
                "tests/test_platform_local_history_export_v27.py",
            }:
                continue
            if not include_v28 and rel_path in {
                "scripts/verify_platform_local_history_state_v28.py",
                "tests/test_platform_local_history_state_v28.py",
            }:
                continue
            if not include_v29 and rel_path in {
                "scripts/verify_platform_local_history_ops_v29.py",
                "tests/test_platform_local_history_ops_v29.py",
            }:
                continue
            if not include_v30 and rel_path in {
                "scripts/verify_platform_local_history_detail_v30.py",
                "tests/test_platform_local_history_detail_v30.py",
            }:
                continue
            self._write_file(root, rel_path, "# verifier\n")
        if not include_v6:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v8:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v7:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v7-query-speed.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v9:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v9-market-source-health.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v10:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v10-persistent-market-cache.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v11:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v11-market-source-ops.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v12:
            for rel_path in (
                "docs/superpowers/plans/2026-07-02-dsa-local-v12-market-prewarm-console.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v13:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v14:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v14-real-use-loop.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v15:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v15-user-query-loop.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v16:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v16-browser-user-loop.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v17:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v17-user-watchlist.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v18:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v18-watchlist-board.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v19:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v19-query-workspace.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v20:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v21:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v22:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v23:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v24:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v25:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v26:
            for rel_path in (
                "docs/superpowers/plans/2026-07-03-dsa-local-v26-history-center-usability.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v27:
            for rel_path in (
                "docs/superpowers/plans/2026-07-04-dsa-local-v27-history-export.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v28:
            for rel_path in (
                "docs/superpowers/plans/2026-07-04-dsa-local-v28-history-state.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v29:
            for rel_path in (
                "docs/superpowers/plans/2026-07-04-dsa-local-v29-history-ops.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v30:
            for rel_path in (
                "docs/superpowers/plans/2026-07-04-dsa-local-v30-history-detail.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()

    def _run_with_fake_git(self, root: Path, *, status_stdout: str = "", ignored_paths: set[str] | None = None):
        from scripts.verify_platform_release_candidate_package import run_release_candidate_checks

        ignored_paths = ignored_paths or set()

        def fake_run(args, **kwargs):
            if args[:3] == ["git", "status", "--short"]:
                return subprocess.CompletedProcess(args=args, returncode=0, stdout=status_stdout, stderr="")
            if args[:3] == ["git", "check-ignore", "-q"]:
                returncode = 0 if args[-1] in ignored_paths else 1
                return subprocess.CompletedProcess(args=args, returncode=returncode, stdout="", stderr="")
            raise AssertionError(f"unexpected command: {args}")

        with patch("scripts.verify_platform_release_candidate_package.subprocess.run", side_effect=fake_run):
            return run_release_candidate_checks(project_root=root)

    def test_reports_missing_release_manifest(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_manifest=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("docs/superpowers/platform-release-candidate-manifest.md", by_id["required_files_present"].metadata["missing_files"])

    def test_reports_missing_local_usability_v6_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v6=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_usability_v6.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_usability_v6.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_query_speed_v7_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v7=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_query_speed_v7.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_query_speed_v7.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v7-query-speed.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_query_resilience_v8_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v8=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_query_resilience_v8.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_query_resilience_v8.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_market_source_health_v9_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v9=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_market_source_health_v9.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_market_source_health_v9.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v9-market-source-health.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_persistent_market_cache_v10_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v10=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_persistent_market_cache_v10.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_persistent_market_cache_v10.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v10-persistent-market-cache.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_market_source_ops_v11_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v11=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_market_source_ops_v11.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("src/services/market_source_ops.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_market_source_ops_v11.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v11-market-source-ops.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_market_prewarm_console_v12_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v12=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_market_prewarm_console_v12.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_market_prewarm_console_v12.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-02-dsa-local-v12-market-prewarm-console.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_market_recovery_console_v13_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v13=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_market_recovery_console_v13.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_market_recovery_console_v13.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_real_use_loop_v14_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v14=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_real_use_loop_v14.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("src/services/local_functional_status.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_real_use_loop_v14.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v14-real-use-loop.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_user_query_loop_v15_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v15=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_user_query_loop_v15.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_user_query_loop_v15.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v15-user-query-loop.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_browser_user_loop_v16_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v16=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_browser_user_loop_v16.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_browser_user_loop_v16.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v16-browser-user-loop.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_watchlist_v17_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v17=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_watchlist_v17.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("src/platform_watchlist.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_watchlist_v17.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_watchlist_v17_verifier.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v17-user-watchlist.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_watchlist_board_v18_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v18=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_watchlist_board_v18.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_watchlist_board_v18.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v18-watchlist-board.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_query_workspace_v19_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v19=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_query_workspace_v19.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_query_workspace_v19.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v19-query-workspace.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_public_entry_v20_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v20=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_public_entry_v20.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_public_entry_v20.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_public_user_flow_v21_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v21=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_public_user_flow_v21.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_public_user_flow_v21.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_market_refresh_v22_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v22=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_market_refresh_v22.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_market_refresh_v22.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_snapshot_boundary_v23_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v23=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_snapshot_boundary_v23.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_snapshot_boundary_v23.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_center_v24_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v24=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_center_v24.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_center_v24.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_center_v25_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v25=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_center_v25.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_center_v25.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_center_v26_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v26=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_center_v26.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_center_v26.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-03-dsa-local-v26-history-center-usability.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_export_v27_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v27=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_export_v27.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_export_v27.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-04-dsa-local-v27-history-export.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_state_v28_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v28=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_state_v28.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_state_v28.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-04-dsa-local-v28-history-state.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_ops_v29_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v29=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_ops_v29.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_ops_v29.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-04-dsa-local-v29-history-ops.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_history_detail_v30_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v30=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_local_history_detail_v30.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_local_history_detail_v30.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-04-dsa-local-v30-history-detail.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_gitignored_verifier(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            results = self._run_with_fake_git(
                root,
                ignored_paths={"scripts/verify_platform_v2_readiness.py"},
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["verifiers_visible_to_git"].status, "failed")
        self.assertIn("scripts/verify_platform_v2_readiness.py", by_id["verifiers_visible_to_git"].metadata["ignored_files"])

    def test_reports_unsafe_production_env_default(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            unsafe_env = SAFE_ENV.replace("BILLING_ENABLED=false", "BILLING_ENABLED=true")
            self._write_minimal_package(root, env_text=unsafe_env)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["prod_env_template_safe"].status, "failed")
        self.assertIn("BILLING_ENABLED", by_id["prod_env_template_safe"].metadata["unsafe_values"])

    def test_reports_dirty_file_missing_from_manifest(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root)

            results = self._run_with_fake_git(
                root,
                status_stdout=" M api/middlewares/auth.py\n?? private-notes.txt\n",
            )

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["dirty_inventory_classified"].status, "failed")
        self.assertIn("private-notes.txt", by_id["dirty_inventory_classified"].metadata["unclassified_files"])
        self.assertEqual(by_id["manifest_covers_dirty_files"].status, "failed")
        self.assertIn("private-notes.txt", by_id["manifest_covers_dirty_files"].metadata["missing_files"])

    def test_classifies_frontend_html_entrypoint(self):
        from scripts.verify_platform_release_candidate_package import classify_dirty_path

        self.assertEqual(
            classify_dirty_path("apps/dsa-web/index.html"),
            "frontend-platform-experience",
        )


if __name__ == "__main__":
    unittest.main()

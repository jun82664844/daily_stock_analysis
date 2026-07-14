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
BILLING_PROVIDER=disabled
BILLING_STRIPE_SECRET_KEY=
BILLING_STRIPE_WEBHOOK_SECRET=
BILLING_STRIPE_PRICE_PRO=
DEBUG=false
CORS_ALLOW_ALL=false
LOCAL_LLM_ENABLED=false
LOCAL_LLM_MAX_CONCURRENT=2
DSA_REAL_PAYMENT_APPROVED=false
DSA_PAYMENT_WEBHOOK_APPROVED=false
DSA_PRODUCTION_DOMAIN_APPROVED=false
DSA_PRODUCTION_HTTPS_APPROVED=false
DSA_PRODUCTION_WAF_APPROVED=false
DSA_MARKET_DATA_LICENSE_APPROVED=false
DSA_LEGAL_TERMS_APPROVED=false
DSA_PRIVACY_POLICY_APPROVED=false
DSA_MONITORING_APPROVED=false
DSA_BACKUP_RESTORE_DRILL_APPROVED=false
DSA_ANALYSIS_NOT_INVESTMENT_ADVICE=true
"""


class PlatformReleaseCandidatePackageVerifierTestCase(unittest.TestCase):
    def test_v119_dynamic_market_home_is_part_of_release_package(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_dynamic_market_home_v119.py", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_dynamic_market_home_v119.py", VERIFIER_FILES)
        self.assertIn("tests/test_platform_dynamic_market_home_v119_verifier.py", REQUIRED_FILES)
        self.assertIn("tests/test_public_market_ranking_service_v119.py", REQUIRED_FILES)
        self.assertIn("src/services/public_market_ranking_service.py", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-14-dsa-v119-dynamic-market-home.md", REQUIRED_FILES)

    def test_v118_public_home_experience_is_part_of_release_package(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_public_home_experience_v118.py", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_public_home_experience_v118.py", VERIFIER_FILES)
        self.assertIn("tests/test_platform_public_home_experience_v118_verifier.py", REQUIRED_FILES)
        self.assertIn("src/services/public_market_index_service.py", REQUIRED_FILES)
        self.assertIn("src/services/public_market_news_service.py", REQUIRED_FILES)
        self.assertIn("tests/test_public_market_index_service_v118.py", REQUIRED_FILES)
        self.assertIn("tests/test_public_market_news_service_v118.py", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-13-dsa-v118-public-home-information-architecture.md", REQUIRED_FILES)

    def test_v117_six_feature_experience_is_part_of_release_package(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_six_feature_experience_v117.py", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_six_feature_experience_v117.py", VERIFIER_FILES)
        self.assertIn("tests/test_platform_six_feature_experience_v117_verifier.py", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/components/market-workspace/marketWorkspaceFormat.ts", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-13-dsa-v117-six-feature-experience-closure.md", REQUIRED_FILES)

    def test_v116_public_market_price_alerts_are_part_of_release_package(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_public_market_price_alerts_v116.py", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_public_market_price_alerts_v116.py", VERIFIER_FILES)
        self.assertIn("src/services/public_market_home_service.py", REQUIRED_FILES)
        self.assertIn("src/services/platform_price_alert_worker.py", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-13-dsa-v116-public-market-home-and-price-alerts.md", REQUIRED_FILES)

    def test_v102_speed_verifier_is_part_of_release_package_contract(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_a_share_free_query_speed_v102.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_a_share_free_query_speed_v102_verifier.py", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-11-dsa-v102-a-share-free-query-speed.md", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_a_share_free_query_speed_v102.py", VERIFIER_FILES)

    def test_v103_cockpit_verifier_is_part_of_release_package_contract(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_free_daily_research_cockpit_v103.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_free_daily_research_cockpit_v103_verifier.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_daily_research_cockpit_v103.py", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/components/radar/DailyResearchCockpitV103.tsx", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/components/radar/__tests__/DailyResearchCockpitV103.test.tsx", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-11-dsa-v103-free-daily-research-cockpit.md", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_free_daily_research_cockpit_v103.py", VERIFIER_FILES)

    def test_v104_market_screening_verifier_is_part_of_release_package_contract(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_market_screening_alerts_v104.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_market_screening_alerts_v104_verifier.py", REQUIRED_FILES)
        self.assertIn("tests/test_market_screening_brief.py", REQUIRED_FILES)
        self.assertIn("src/services/market_screening_brief.py", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-11-dsa-v104-explainable-stock-discovery.md", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_market_screening_alerts_v104.py", VERIFIER_FILES)

    def test_v105_fast_useful_screening_verifier_is_part_of_release_package_contract(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_fast_useful_screening_v105.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_fast_useful_screening_v105_verifier.py", REQUIRED_FILES)
        self.assertIn("tests/test_alphasift_screen_cache_v105.py", REQUIRED_FILES)
        self.assertIn("src/services/alphasift_screen_cache.py", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-11-dsa-v105-fast-useful-market-screening.md", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_fast_useful_screening_v105.py", VERIFIER_FILES)

    def test_v106_financial_research_verifier_is_part_of_release_package_contract(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_financial_research_workflows_v106.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_financial_research_workflows_v106_verifier.py", REQUIRED_FILES)
        self.assertIn("tests/test_financial_research_workflow_service_v106.py", REQUIRED_FILES)
        self.assertIn("src/services/financial_research_workflow_service.py", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/pages/ResearchWorkflowsPage.tsx", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-11-dsa-v106-financial-research-workflows.md", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_financial_research_workflows_v106.py", VERIFIER_FILES)

    def test_v107_ollama_retention_verifier_is_part_of_release_package_contract(self) -> None:
        from scripts.verify_platform_release_candidate_package import REQUIRED_FILES, VERIFIER_FILES

        self.assertIn("scripts/verify_platform_ollama_local_retention_v107.py", REQUIRED_FILES)
        self.assertIn("tests/test_platform_ollama_local_retention_v107_verifier.py", REQUIRED_FILES)
        self.assertIn("tests/test_ollama_runtime_service_v107.py", REQUIRED_FILES)
        self.assertIn("src/services/ollama_runtime_service.py", REQUIRED_FILES)
        self.assertIn("apps/dsa-web/src/components/retention/LocalModelStatusV107.tsx", REQUIRED_FILES)
        self.assertIn("docs/superpowers/plans/2026-07-11-dsa-v107-ollama-local-retention.md", REQUIRED_FILES)
        self.assertIn("scripts/verify_platform_ollama_local_retention_v107.py", VERIFIER_FILES)

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
        include_v48: bool = True,
        include_v49: bool = True,
        include_v50: bool = True,
        include_v51: bool = True,
        include_v52: bool = True,
        include_v53: bool = True,
        include_v54: bool = True,
        include_v55: bool = True,
        include_v56: bool = True,
        include_v57: bool = True,
        include_v58: bool = True,
        include_v59: bool = True,
        include_v60: bool = True,
        include_v61: bool = True,
        include_v62: bool = True,
        include_v63: bool = True,
        include_v64: bool = True,
        include_v65: bool = True,
        include_v66: bool = True,
        include_v67: bool = True,
        include_v68: bool = True,
        include_v69: bool = True,
        include_v70: bool = True,
        include_v71: bool = True,
        include_v72: bool = True,
        include_v73: bool = True,
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
            "docs/superpowers/plans/2026-07-05-dsa-production-readiness-v48.md": (
                "No-go\nGO/NO-GO\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nProduction readiness\nNo real payment\n"
                "DSA_PLATFORM_PRODUCTION_READINESS_V48_OK\n"
            ),
            "docs/superpowers/plans/2026-07-05-dsa-billing-provider-boundary-v49.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo real payment\n"
                "DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK\n"
            ),
            "docs/superpowers/plans/2026-07-05-dsa-production-env-gates-v50.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nsafe defaults\n"
                "DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK\n"
            ),
            "docs/superpowers/plans/2026-07-05-dsa-backup-restore-drill-v51.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\ndoes not delete\nNo AI calls\n"
                "DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK\n"
            ),
            "docs/superpowers/plans/2026-07-05-dsa-ops-health-v52.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nAdmin-only\nRead-only\n"
                "DSA_PLATFORM_OPS_HEALTH_V52_OK\n"
            ),
            "docs/superpowers/plans/2026-07-05-dsa-ops-health-panel-v53.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nsecret-free\n"
                "DSA_PLATFORM_OPS_HEALTH_PANEL_V53_OK\n"
            ),
            "docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nanonymous\nNo AI\n"
                "DSA_PLATFORM_LOCAL_USER_ACCEPTANCE_V54_OK\n"
            ),
            "docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nguest-query-entry\nretention_brief\n"
                "guest-conversion-guide\nDSA_PLATFORM_LOCAL_PRODUCT_EXPERIENCE_V55_OK\n"
            ),
            "docs/superpowers/plans/2026-07-06-dsa-v56-user-retention-loop.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nguest AAPL\nsave history\nwatchlist\n"
                "DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK\n"
            ),
            "docs/superpowers/plans/2026-07-06-dsa-v57-news-kline-forecast-lab.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\nKronos-ready\n"
                "DSA_PLATFORM_LOCAL_NEWS_KLINE_V57_OK\n"
            ),
            "docs/superpowers/plans/2026-07-06-dsa-v58-kronos-sandbox.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nKRONOS_ENABLED\nmodel_unavailable\n"
                "DSA_PLATFORM_KRONOS_SANDBOX_V58_OK\n"
            ),
            "docs/superpowers/plans/2026-07-07-dsa-v59-a-stock-data-poc.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "a-stock-data\nA-share enrichment\n"
                "DSA_PLATFORM_A_STOCK_DATA_POC_V59_OK\n"
            ),
            "docs/superpowers/plans/2026-07-07-dsa-v60-a-stock-data-source.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nexternal calls disabled by default\n"
                "a-stock-data\ncache\nrate limit\nDSA_PLATFORM_A_STOCK_DATA_V60_OK\n"
            ),
            "docs/superpowers/plans/2026-07-07-dsa-v61-a-stock-data-ui.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\na-stock-data\n600519\n000001\n"
                "DSA_PLATFORM_A_STOCK_DATA_UI_V61_OK\n"
            ),
            "docs/superpowers/plans/2026-07-07-dsa-v62-a-stock-data-useful.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "a-stock-data\nCNINFO\nEastmoney\n"
                "DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v63-a-stock-data-experience.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "reader_summary\nDSA_PLATFORM_A_STOCK_DATA_EXPERIENCE_V63_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v64-a-stock-data-details.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "details\nDSA_PLATFORM_A_STOCK_DATA_DETAILS_V64_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v65-free-value-experience.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free value summary\nDSA_PLATFORM_FREE_VALUE_V65_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v66-productized-snapshot.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "same visible modules\nfree web source\npremium API source\n"
                "DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v67-free-research-board.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free research board\nnews radar\nK-line read\npeer and sector\nrisk explanation\n"
                "DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v68-free-commercial-journey.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free commercial journey\nsame visible modules\npremium changes data source\n"
                "guest query works\nDSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v69-free-data-depth.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free data depth\nsame visible modules\nA-share\nUS equity\n"
                "DSA_PLATFORM_FREE_DATA_DEPTH_V69_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v70-free-detail-readability.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free detail readability\nsame visible modules\nexpand details\n"
                "event checklist\npeer comparison table\nK-line triggers\n"
                "DSA_PLATFORM_FREE_DETAIL_READABILITY_V70_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v71-free-multimarket-modules.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free multimarket modules\nsame visible modules\nA-share\nUS equity\n"
                "HK equity\ncrypto\npeer comparison table\nK-line triggers\n"
                "DSA_PLATFORM_FREE_MULTIMARKET_V71_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v72-free-peer-quotes.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "free peer reference quotes\nsame visible modules\nshort timeout\n"
                "API-backed sources\nDSA_PLATFORM_FREE_PEER_QUOTES_V72_OK\n"
            ),
            "docs/superpowers/plans/2026-07-08-dsa-v73-free-broker-conversion.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "DSA V73 Free Broker Conversion Implementation Plan\n"
                "broker-style decision cockpit\nbasic-query-broker-cockpit\n"
                "DSA_PLATFORM_FREE_BROKER_CONVERSION_V73_OK\n"
            ),
            "docs/superpowers/plans/2026-07-11-dsa-v102-a-share-free-query-speed.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "DSA V102 A-share Free Query Speed Implementation Plan\n"
                "bounded parallel enrichment\nshared cache\n"
                "DSA_PLATFORM_A_SHARE_FREE_QUERY_SPEED_V102_OK\n"
            ),
            "docs/superpowers/plans/2026-07-11-dsa-v103-free-daily-research-cockpit.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls\nNo public search\n"
                "DSA V103 Free Daily Research Cockpit Implementation Plan\n"
                "daily research cockpit\ndata confidence\nAPI trial\n"
                "DSA_PLATFORM_FREE_DAILY_RESEARCH_COCKPIT_V103_OK\n"
            ),
            "docs/superpowers/plans/2026-07-11-dsa-v104-explainable-stock-discovery.md": (
                "No-go\nlocal-only\nnot real payment\nnot investment advice\n"
                "Do not commit real API Key\nNo AI calls by default\nNo public search\n"
                "DSA V104 market data screening and condition alerts\n"
                "information and data only\nuser-defined alerts\n"
                "DSA_PLATFORM_MARKET_SCREENING_ALERTS_V104_OK\n"
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
            "scripts/verify_platform_production_readiness_v48.py",
            "scripts/verify_platform_billing_provider_boundary_v49.py",
            "scripts/verify_platform_production_env_gates_v50.py",
            "scripts/verify_platform_backup_restore_drill_v51.py",
            "scripts/verify_platform_ops_health_v52.py",
            "scripts/verify_platform_ops_health_panel_v53.py",
            "scripts/verify_platform_local_user_acceptance_v54.py",
            "scripts/verify_platform_local_product_experience_v55.py",
            "scripts/verify_platform_local_user_retention_v56.py",
            "scripts/verify_platform_local_news_kline_v57.py",
            "scripts/verify_platform_kronos_sandbox_v58.py",
            "scripts/verify_platform_a_stock_data_poc_v59.py",
            "scripts/verify_platform_a_stock_data_v60.py",
            "scripts/verify_platform_a_stock_data_ui_v61.py",
            "scripts/verify_platform_a_stock_data_useful_v62.py",
            "scripts/verify_platform_a_stock_data_experience_v63.py",
            "scripts/verify_platform_a_stock_data_details_v64.py",
            "scripts/verify_platform_free_value_v65.py",
            "scripts/verify_platform_productized_snapshot_v66.py",
            "scripts/verify_platform_free_research_board_v67.py",
            "scripts/verify_platform_free_commercial_journey_v68.py",
            "scripts/verify_platform_free_data_depth_v69.py",
            "scripts/verify_platform_free_detail_readability_v70.py",
            "scripts/verify_platform_free_multimarket_v71.py",
            "scripts/verify_platform_free_peer_quotes_v72.py",
            "scripts/verify_platform_free_broker_conversion_v73.py",
            "scripts/verify_platform_a_share_free_query_speed_v102.py",
            "scripts/verify_platform_free_daily_research_cockpit_v103.py",
            "scripts/verify_platform_market_screening_alerts_v104.py",
            "scripts/verify_platform_fast_useful_screening_v105.py",
            "scripts/run_platform_backup_restore_dry_run.py",
            "scripts/cleanup_platform_e2e_data.py",
            "src/platform_watchlist.py",
            "src/services/a_share_enrichment_service.py",
            "src/services/kronos_forecast_service.py",
            "src/services/market_source_ops.py",
            "src/services/local_functional_status.py",
            "src/services/production_readiness.py",
            "src/services/platform_backup.py",
            "src/services/platform_ops_health.py",
            "src/notification_sender/feishu_sender.py",
            "tests/test_platform_release_candidate_package.py",
            "tests/test_feishu_sender_import_resilience.py",
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
            "tests/test_platform_production_readiness_v48.py",
            "tests/test_billing_provider_boundary_v49.py",
            "tests/test_platform_production_env_gates_v50.py",
            "tests/test_platform_backup_restore_drill_v51.py",
            "tests/test_platform_ops_health_v52.py",
            "tests/test_platform_local_user_acceptance_v54.py",
            "tests/test_platform_local_product_experience_v55.py",
            "tests/test_platform_local_user_retention_v56.py",
            "tests/test_platform_local_news_kline_v57.py",
            "tests/test_kronos_forecast_service_v58.py",
            "tests/test_kronos_forecast_api_v58.py",
            "tests/test_platform_kronos_sandbox_v58.py",
            "tests/test_a_share_enrichment_service.py",
            "tests/test_platform_a_stock_data_poc_v59.py",
            "tests/test_platform_a_stock_data_v60.py",
            "tests/test_platform_a_stock_data_ui_v61.py",
            "tests/test_platform_a_stock_data_useful_v62.py",
            "tests/test_platform_a_stock_data_experience_v63.py",
            "tests/test_platform_a_stock_data_details_v64.py",
            "tests/test_platform_free_value_v65.py",
            "tests/test_platform_productized_snapshot_v66.py",
            "tests/test_platform_free_research_board_v67.py",
            "tests/test_platform_free_commercial_journey_v68.py",
            "tests/test_platform_free_data_depth_v69.py",
            "tests/test_platform_free_detail_readability_v70.py",
            "tests/test_platform_free_multimarket_v71.py",
            "tests/test_platform_free_peer_quotes_v72.py",
            "tests/test_platform_free_broker_conversion_v73.py",
            "tests/test_platform_a_share_free_query_speed_v102_verifier.py",
            "tests/test_platform_daily_research_cockpit_v103.py",
            "tests/test_platform_free_daily_research_cockpit_v103_verifier.py",
            "apps/dsa-web/src/components/radar/DailyResearchCockpitV103.tsx",
            "apps/dsa-web/src/components/radar/__tests__/DailyResearchCockpitV103.test.tsx",
            "src/services/market_screening_brief.py",
            "tests/test_market_screening_brief.py",
            "tests/test_platform_market_screening_alerts_v104_verifier.py",
            "src/services/alphasift_screen_cache.py",
            "tests/test_alphasift_screen_cache_v105.py",
            "tests/test_platform_fast_useful_screening_v105_verifier.py",
            "docs/superpowers/plans/2026-07-11-dsa-v105-fast-useful-market-screening.md",
            "apps/dsa-web/src/components/screening/screeningModelV104.ts",
            "apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx",
            "apps/dsa-web/src/components/screening/ScreeningCompareTrayV104.tsx",
            "apps/dsa-web/src/components/screening/ScreeningReminderPanelV104.tsx",
            "apps/dsa-web/src/components/screening/__tests__/screeningModelV104.test.ts",
            "apps/dsa-web/src/components/screening/__tests__/MarketScreeningCardV104.test.tsx",
            "apps/dsa-web/src/components/screening/__tests__/ScreeningCompareTrayV104.test.tsx",
            "apps/dsa-web/src/components/screening/__tests__/ScreeningReminderPanelV104.test.tsx",
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
            if not include_v48 and rel_path in {
                "scripts/verify_platform_production_readiness_v48.py",
                "src/services/production_readiness.py",
                "tests/test_platform_production_readiness_v48.py",
            }:
                continue
            if not include_v49 and rel_path in {
                "scripts/verify_platform_billing_provider_boundary_v49.py",
                "tests/test_billing_provider_boundary_v49.py",
            }:
                continue
            if not include_v50 and rel_path in {
                "scripts/verify_platform_production_env_gates_v50.py",
                "tests/test_platform_production_env_gates_v50.py",
            }:
                continue
            if not include_v51 and rel_path in {
                "scripts/verify_platform_backup_restore_drill_v51.py",
                "scripts/run_platform_backup_restore_dry_run.py",
                "src/services/platform_backup.py",
                "tests/test_platform_backup_restore_drill_v51.py",
            }:
                continue
            if not include_v52 and rel_path in {
                "scripts/verify_platform_ops_health_v52.py",
                "src/services/platform_ops_health.py",
                "tests/test_platform_ops_health_v52.py",
            }:
                continue
            if not include_v53 and rel_path in {
                "scripts/verify_platform_ops_health_panel_v53.py",
            }:
                continue
            if not include_v54 and rel_path in {
                "scripts/verify_platform_local_user_acceptance_v54.py",
                "tests/test_platform_local_user_acceptance_v54.py",
            }:
                continue
            if not include_v55 and rel_path in {
                "scripts/verify_platform_local_product_experience_v55.py",
                "tests/test_platform_local_product_experience_v55.py",
            }:
                continue
            if not include_v56 and rel_path in {
                "scripts/verify_platform_local_user_retention_v56.py",
                "tests/test_platform_local_user_retention_v56.py",
            }:
                continue
            if not include_v57 and rel_path in {
                "scripts/verify_platform_local_news_kline_v57.py",
                "tests/test_platform_local_news_kline_v57.py",
            }:
                continue
            if not include_v58 and rel_path in {
                "scripts/verify_platform_kronos_sandbox_v58.py",
                "src/services/kronos_forecast_service.py",
                "tests/test_kronos_forecast_service_v58.py",
                "tests/test_kronos_forecast_api_v58.py",
                "tests/test_platform_kronos_sandbox_v58.py",
            }:
                continue
            if not include_v59 and rel_path in {
                "scripts/verify_platform_a_stock_data_poc_v59.py",
                "src/services/a_share_enrichment_service.py",
                "tests/test_a_share_enrichment_service.py",
                "tests/test_platform_a_stock_data_poc_v59.py",
            }:
                continue
            if not include_v60 and rel_path in {
                "scripts/verify_platform_a_stock_data_v60.py",
                "tests/test_platform_a_stock_data_v60.py",
            }:
                continue
            if not include_v61 and rel_path in {
                "scripts/verify_platform_a_stock_data_ui_v61.py",
                "tests/test_platform_a_stock_data_ui_v61.py",
            }:
                continue
            if not include_v62 and rel_path in {
                "scripts/verify_platform_a_stock_data_useful_v62.py",
                "tests/test_platform_a_stock_data_useful_v62.py",
            }:
                continue
            if not include_v63 and rel_path in {
                "scripts/verify_platform_a_stock_data_experience_v63.py",
                "tests/test_platform_a_stock_data_experience_v63.py",
            }:
                continue
            if not include_v64 and rel_path in {
                "scripts/verify_platform_a_stock_data_details_v64.py",
                "tests/test_platform_a_stock_data_details_v64.py",
            }:
                continue
            if not include_v65 and rel_path in {
                "scripts/verify_platform_free_value_v65.py",
                "tests/test_platform_free_value_v65.py",
            }:
                continue
            if not include_v66 and rel_path in {
                "scripts/verify_platform_productized_snapshot_v66.py",
                "tests/test_platform_productized_snapshot_v66.py",
            }:
                continue
            if not include_v67 and rel_path in {
                "scripts/verify_platform_free_research_board_v67.py",
                "tests/test_platform_free_research_board_v67.py",
            }:
                continue
            if not include_v68 and rel_path in {
                "scripts/verify_platform_free_commercial_journey_v68.py",
                "tests/test_platform_free_commercial_journey_v68.py",
            }:
                continue
            if not include_v69 and rel_path in {
                "scripts/verify_platform_free_data_depth_v69.py",
                "tests/test_platform_free_data_depth_v69.py",
            }:
                continue
            if not include_v70 and rel_path in {
                "scripts/verify_platform_free_detail_readability_v70.py",
                "tests/test_platform_free_detail_readability_v70.py",
            }:
                continue
            if not include_v71 and rel_path in {
                "scripts/verify_platform_free_multimarket_v71.py",
                "tests/test_platform_free_multimarket_v71.py",
            }:
                continue
            if not include_v72 and rel_path in {
                "scripts/verify_platform_free_peer_quotes_v72.py",
                "tests/test_platform_free_peer_quotes_v72.py",
            }:
                continue
            if not include_v73 and rel_path in {
                "scripts/verify_platform_free_broker_conversion_v73.py",
                "tests/test_platform_free_broker_conversion_v73.py",
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
        if not include_v48:
            for rel_path in (
                "docs/superpowers/plans/2026-07-05-dsa-production-readiness-v48.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v49:
            for rel_path in (
                "docs/superpowers/plans/2026-07-05-dsa-billing-provider-boundary-v49.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v50:
            for rel_path in (
                "docs/superpowers/plans/2026-07-05-dsa-production-env-gates-v50.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v51:
            for rel_path in (
                "docs/superpowers/plans/2026-07-05-dsa-backup-restore-drill-v51.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v52:
            for rel_path in (
                "docs/superpowers/plans/2026-07-05-dsa-ops-health-v52.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v53:
            for rel_path in (
                "docs/superpowers/plans/2026-07-05-dsa-ops-health-panel-v53.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v54:
            for rel_path in (
                "docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v55:
            for rel_path in (
                "docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v56:
            for rel_path in (
                "docs/superpowers/plans/2026-07-06-dsa-v56-user-retention-loop.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v57:
            for rel_path in (
                "docs/superpowers/plans/2026-07-06-dsa-v57-news-kline-forecast-lab.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v58:
            for rel_path in (
                "docs/superpowers/plans/2026-07-06-dsa-v58-kronos-sandbox.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v59:
            for rel_path in (
                "docs/superpowers/plans/2026-07-07-dsa-v59-a-stock-data-poc.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v60:
            for rel_path in (
                "docs/superpowers/plans/2026-07-07-dsa-v60-a-stock-data-source.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v61:
            for rel_path in (
                "docs/superpowers/plans/2026-07-07-dsa-v61-a-stock-data-ui.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v62:
            for rel_path in (
                "docs/superpowers/plans/2026-07-07-dsa-v62-a-stock-data-useful.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v63:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v63-a-stock-data-experience.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v64:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v64-a-stock-data-details.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v65:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v65-free-value-experience.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v66:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v66-productized-snapshot.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v67:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v67-free-research-board.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v68:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v68-free-commercial-journey.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v69:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v69-free-data-depth.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v70:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v70-free-detail-readability.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v71:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v71-free-multimarket-modules.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v72:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v72-free-peer-quotes.md",
            ):
                path = root / rel_path
                if path.exists():
                    path.unlink()
        if not include_v73:
            for rel_path in (
                "docs/superpowers/plans/2026-07-08-dsa-v73-free-broker-conversion.md",
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

    def test_reports_missing_production_readiness_v48_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v48=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_production_readiness_v48.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("src/services/production_readiness.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_production_readiness_v48.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-05-dsa-production-readiness-v48.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_billing_provider_boundary_v49_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v49=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_billing_provider_boundary_v49.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_billing_provider_boundary_v49.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-05-dsa-billing-provider-boundary-v49.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_production_env_gates_v50_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v50=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_production_env_gates_v50.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_production_env_gates_v50.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-05-dsa-production-env-gates-v50.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_backup_restore_drill_v51_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v51=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_backup_restore_drill_v51.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("scripts/run_platform_backup_restore_dry_run.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("src/services/platform_backup.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_backup_restore_drill_v51.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-05-dsa-backup-restore-drill-v51.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_ops_health_v52_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v52=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_ops_health_v52.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("src/services/platform_ops_health.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn("tests/test_platform_ops_health_v52.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-05-dsa-ops-health-v52.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_ops_health_panel_v53_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v53=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn("scripts/verify_platform_ops_health_panel_v53.py", by_id["required_files_present"].metadata["missing_files"])
        self.assertIn(
            "docs/superpowers/plans/2026-07-05-dsa-ops-health-panel-v53.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_user_acceptance_v54_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v54=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_user_acceptance_v54.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "tests/test_platform_local_user_acceptance_v54.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_product_experience_v55_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v55=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_product_experience_v55.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "tests/test_platform_local_product_experience_v55.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_user_retention_v56_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v56=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_user_retention_v56.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "tests/test_platform_local_user_retention_v56.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "docs/superpowers/plans/2026-07-06-dsa-v56-user-retention-loop.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_local_news_kline_v57_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v57=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        self.assertIn(
            "scripts/verify_platform_local_news_kline_v57.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "tests/test_platform_local_news_kline_v57.py",
            by_id["required_files_present"].metadata["missing_files"],
        )
        self.assertIn(
            "docs/superpowers/plans/2026-07-06-dsa-v57-news-kline-forecast-lab.md",
            by_id["required_files_present"].metadata["missing_files"],
        )

    def test_reports_missing_kronos_sandbox_v58_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v58=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_kronos_sandbox_v58.py", missing)
        self.assertIn("src/services/kronos_forecast_service.py", missing)
        self.assertIn("tests/test_kronos_forecast_service_v58.py", missing)
        self.assertIn("tests/test_kronos_forecast_api_v58.py", missing)
        self.assertIn("tests/test_platform_kronos_sandbox_v58.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-06-dsa-v58-kronos-sandbox.md", missing)

    def test_reports_missing_a_stock_data_poc_v59_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v59=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_a_stock_data_poc_v59.py", missing)
        self.assertIn("src/services/a_share_enrichment_service.py", missing)
        self.assertIn("tests/test_a_share_enrichment_service.py", missing)
        self.assertIn("tests/test_platform_a_stock_data_poc_v59.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-07-dsa-v59-a-stock-data-poc.md", missing)

    def test_reports_missing_a_stock_data_v60_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v60=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_a_stock_data_v60.py", missing)
        self.assertIn("tests/test_platform_a_stock_data_v60.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-07-dsa-v60-a-stock-data-source.md", missing)

    def test_reports_missing_a_stock_data_ui_v61_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v61=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_a_stock_data_ui_v61.py", missing)
        self.assertIn("tests/test_platform_a_stock_data_ui_v61.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-07-dsa-v61-a-stock-data-ui.md", missing)

    def test_reports_missing_a_stock_data_useful_v62_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v62=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_a_stock_data_useful_v62.py", missing)
        self.assertIn("tests/test_platform_a_stock_data_useful_v62.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-07-dsa-v62-a-stock-data-useful.md", missing)

    def test_reports_missing_a_stock_data_experience_v63_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v63=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_a_stock_data_experience_v63.py", missing)
        self.assertIn("tests/test_platform_a_stock_data_experience_v63.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v63-a-stock-data-experience.md", missing)

    def test_reports_missing_a_stock_data_details_v64_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v64=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_a_stock_data_details_v64.py", missing)
        self.assertIn("tests/test_platform_a_stock_data_details_v64.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v64-a-stock-data-details.md", missing)

    def test_reports_missing_free_value_v65_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v65=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_value_v65.py", missing)
        self.assertIn("tests/test_platform_free_value_v65.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v65-free-value-experience.md", missing)

    def test_reports_missing_productized_snapshot_v66_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v66=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_productized_snapshot_v66.py", missing)
        self.assertIn("tests/test_platform_productized_snapshot_v66.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v66-productized-snapshot.md", missing)

    def test_reports_missing_free_research_board_v67_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v67=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_research_board_v67.py", missing)
        self.assertIn("tests/test_platform_free_research_board_v67.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v67-free-research-board.md", missing)

    def test_reports_missing_free_commercial_journey_v68_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v68=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_commercial_journey_v68.py", missing)
        self.assertIn("tests/test_platform_free_commercial_journey_v68.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v68-free-commercial-journey.md", missing)

    def test_reports_missing_free_data_depth_v69_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v69=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_data_depth_v69.py", missing)
        self.assertIn("tests/test_platform_free_data_depth_v69.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v69-free-data-depth.md", missing)

    def test_reports_missing_free_detail_readability_v70_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v70=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_detail_readability_v70.py", missing)
        self.assertIn("tests/test_platform_free_detail_readability_v70.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v70-free-detail-readability.md", missing)

    def test_reports_missing_free_multimarket_v71_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v71=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_multimarket_v71.py", missing)
        self.assertIn("tests/test_platform_free_multimarket_v71.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v71-free-multimarket-modules.md", missing)

    def test_reports_missing_free_peer_quotes_v72_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v72=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_peer_quotes_v72.py", missing)
        self.assertIn("tests/test_platform_free_peer_quotes_v72.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v72-free-peer-quotes.md", missing)

    def test_reports_missing_free_broker_conversion_v73_files(self):
        with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as temp_dir:
            root = Path(temp_dir)
            self._write_minimal_package(root, include_v73=False)

            results = self._run_with_fake_git(root)

        by_id = {result.check_id: result for result in results}
        self.assertEqual(by_id["required_files_present"].status, "failed")
        missing = by_id["required_files_present"].metadata["missing_files"]
        self.assertIn("scripts/verify_platform_free_broker_conversion_v73.py", missing)
        self.assertIn("tests/test_platform_free_broker_conversion_v73.py", missing)
        self.assertIn("docs/superpowers/plans/2026-07-08-dsa-v73-free-broker-conversion.md", missing)

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

    def test_classifies_local_env_example(self):
        from scripts.verify_platform_release_candidate_package import classify_dirty_path

        self.assertEqual(classify_dirty_path(".env.example"), "docs-and-config")

    def test_classifies_backup_restore_runner(self):
        from scripts.verify_platform_release_candidate_package import classify_dirty_path

        self.assertEqual(
            classify_dirty_path("scripts/run_platform_backup_restore_dry_run.py"),
            "tests-and-verifiers",
        )


if __name__ == "__main__":
    unittest.main()

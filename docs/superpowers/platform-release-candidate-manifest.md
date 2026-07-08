# DSA Platform Release Candidate Manifest

Date: 2026-07-02

Scope: manifest for reviewing and later splitting the local V1/V2 platform release-candidate package. This file is a review aid only. It does not approve public launch, real payment, production deployment, or production secret use.

No-go: real payment disabled, no production API keys, no public deployment, no HTTPS/domain/WAF claims, no legal/privacy finalization, and no investment advice. 不构成投资建议. Do not commit real API Key.

## Summary

Current expected package size after the local billing lifecycle gate, Query Quality V4 gate, Local Functional V5 gate, Local Usability V6 gate, Local Query Speed V7 gate, Local Query Resilience V8 gate, Local Market Source Health V9 gate, Local Persistent Market Cache V10 gate, Local Market Source Ops V11 gate, Local Market Prewarm Console V12 gate, Local Market Recovery Console V13 gate, Local Real Use Loop V14 gate, Local User Query Loop V15 gate, Local Browser User Loop V16 gate, Local Watchlist V17 gate, Local Watchlist Board V18 gate, Local Query Workspace V19 gate, Local Public Entry V20 gate, Local Public User Flow V21 gate, Local Market Refresh V22 gate, Local History Snapshot Boundary V23 gate, Local History Center V24/V25 gates, Local History Center Usability V26 gate, Local History Export V27 gate, Local History State V28 gate, Local History Operations V29 gate, and Local History Detail V30 gate are present:

- modified: 40
- untracked: 147
- deleted: 0
- total dirty entries: 187

Recommended commit order, after human review only:

1. `backend-platform-foundation`
2. `frontend-platform-experience`
3. `tests-and-verifiers`
4. `docs-and-config`
5. `build-and-ignore-impact`
6. `manual-confirmation`

## Slice: backend-platform-foundation

Purpose: platform backend behavior for auth, CSRF, platform accounts, local sandbox billing lifecycle, billing-disabled boundary, quota lanes, write endpoint rate limits, user API key custody, history/task isolation, local model/no-AI support, Query Quality V4 market routing, V9 source-health/prewarm support, V10 persistent market cache fallback, V11 source-ops diagnostics, V12 no-AI prewarm compatibility, V13 admin-only source recovery, and V14 local functional status.

Risk: highest behavioral blast radius. A bad change here can bypass auth, leak API keys, miscount quota, expose another user's history, let abuse bypass local throttles, accidentally enable payment, or route quick queries into expensive AI paths.

Suggested verification:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_api tests.test_platform_accounts tests.test_platform_security_boundaries tests.test_platform_api_keys_product tests.test_platform_audit tests.test_platform_feature_policy tests.test_billing_api tests.test_local_v1_operability
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_billing_sandbox_flow tests.test_billing_subscription_lifecycle
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_user_e2e_safety
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_query_quality_v4
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_functional_v5
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_usability_v6
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_speed_v7
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_resilience_v8
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_source_health_v9
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_persistent_market_cache_v10
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_source_ops_v11
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_recovery_console_v13
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_real_use_loop_v14
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_user_query_loop_v15
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_browser_user_loop_v16
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_watchlist_v17 tests.test_platform_local_watchlist_v17_verifier
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_watchlist_board_v18
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_workspace_v19
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_public_entry_v20
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_public_user_flow_v21
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_refresh_v22
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_export_v27
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_state_v28
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_ops_v29
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_detail_v30
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_query_quality_v4.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_functional_v5.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_usability_v6.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_speed_v7.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_resilience_v8.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_source_health_v9.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_persistent_market_cache_v10.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_source_ops_v11.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_prewarm_console_v12.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_recovery_console_v13.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_real_use_loop_v14.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_user_query_loop_v15.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_browser_user_loop_v16.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_watchlist_v17.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_watchlist_board_v18.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_workspace_v19.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_public_entry_v20.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_public_user_flow_v21.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_refresh_v22.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_export_v27.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_state_v28.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_ops_v29.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_detail_v30.py
```

Rollback note: roll back backend schema/service/API files as one slice. Do not partially revert `src/storage.py` without checking platform tables and `analysis_history.platform_user_id` migration behavior.

Files:

- `api/app.py`
- `api/middlewares/auth.py`
- `api/v1/endpoints/analysis.py`
- `api/v1/endpoints/auth.py`
- `api/v1/endpoints/history.py`
- `api/v1/endpoints/stocks.py`
- `api/v1/router.py`
- `api/v1/schemas/analysis.py`
- `api/v1/endpoints/billing.py`
- `api/v1/endpoints/platform.py`
- `api/v1/schemas/basic_query.py`
- `api/v1/schemas/billing.py`
- `api/v1/schemas/history.py`
- `api/v1/schemas/platform.py`
- `src/core/market_review.py`
- `src/core/pipeline.py`
- `src/services/analysis_service.py`
- `src/services/history_service.py`
- `src/services/stock_code_utils.py`
- `src/services/stock_service.py`
- `src/services/task_queue.py`
- `src/storage.py`
- `src/billing/__init__.py`
- `src/billing/lifecycle.py`
- `src/billing/payment_provider.py`
- `src/csrf.py`
- `src/llm/local_model_router.py`
- `src/platform_accounts.py`
- `src/platform_audit.py`
- `src/platform_feature_policy.py`
- `src/platform_rate_limit.py`
- `src/platform_watchlist.py`
- `src/services/basic_query_service.py`
- `src/services/market_data_cache.py`
- `src/services/market_source_health.py`
- `src/services/persistent_market_data_cache.py`
- `src/services/market_source_ops.py`
- `src/services/local_functional_status.py`

## Slice: frontend-platform-experience

Purpose: React/Vite platform UX, AccountPage, AdminPage, platform API client, HomePage/basic query affordances, Query Quality V4 quick-query degradation display, V7 timing/cache diagnostics, V8 fallback diagnostics, V9 source-health/prewarm diagnostics, V10 persistent-cache diagnostics, V11 source-ops panel, V12 AdminPage prewarm console, V13 AdminPage recovery console, V14 local functional status panel, V15 ordinary-user query guardrails, V16 browser user loop guardrails, V18 watchlist board rows, V19 query workspace separation, navigation, text, and frontend state.

Risk: medium. Main risks are leaking redacted metadata in AdminPage, exposing plaintext user API keys in AccountPage, confusing basic query with AI/deep analysis, hiding stale/missing-data warnings, breaking admin navigation, or omitting not-investment-advice copy.

Suggested verification:

```powershell
cd apps\dsa-web
npm test -- --run src/api/__tests__/index.test.ts src/api/__tests__/platform.test.ts src/pages/__tests__/AdminPage.test.tsx src/pages/__tests__/AccountPage.test.tsx src/components/layout/__tests__/SidebarNav.test.tsx
npm test -- --run src/api/__tests__/stocks.test.ts src/pages/__tests__/HomePage.test.tsx
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "marks historical reports"
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "filters the history center"
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "restores history center filters"
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "exports selected history reports"
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "watchlist board"
npm test -- --run src/components/layout/__tests__/RouteBoundary.test.tsx
npm run build
cd ..\..
```

Rollback note: roll back frontend files together with matching frontend tests. Do not delete `static/`; rebuild if static assets need refreshing.

Files:

- `apps/dsa-web/index.html`
- `apps/dsa-web/src/App.test.tsx`
- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/api/analysis.ts`
- `apps/dsa-web/src/api/history.ts`
- `apps/dsa-web/src/api/index.ts`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/components/history/HistoryList.tsx`
- `apps/dsa-web/src/components/history/HistoryListItem.tsx`
- `apps/dsa-web/src/components/report/ReportSummary.tsx`
- `apps/dsa-web/src/components/layout/RouteBoundary.tsx`
- `apps/dsa-web/src/components/layout/__tests__/RouteBoundary.test.tsx`
- `apps/dsa-web/src/components/layout/ShellHeader.tsx`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`
- `apps/dsa-web/src/hooks/useHomeDashboardState.ts`
- `apps/dsa-web/src/i18n/uiText.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/types/analysis.ts`
- `apps/dsa-web/src/utils/downloadText.ts`
- `apps/dsa-web/src/api/__tests__/analysis.test.ts`
- `apps/dsa-web/src/api/__tests__/index.test.ts`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/pages/AccountPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx`
- `apps/dsa-web/src/pages/AdminPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`

## Slice: tests-and-verifiers

Purpose: automated proof for platform behavior, local V1 operability, V2 readiness, and this release-candidate package boundary.

Risk: low to medium. Bad verifier logic can hide an unsafe release package or fail to catch ignored scripts, dangerous env defaults, or unclassified dirty files.

Suggested verification:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_release_candidate_package
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_speed_v7
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_resilience_v8
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_source_health_v9
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_persistent_market_cache_v10
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_source_ops_v11
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_prewarm_console_v12
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_recovery_console_v13
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_real_use_loop_v14
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_user_query_loop_v15
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_browser_user_loop_v16
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_watchlist_v17 tests.test_platform_local_watchlist_v17_verifier
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_watchlist_board_v18
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_workspace_v19
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_public_entry_v20
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_public_user_flow_v21
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_market_refresh_v22
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_snapshot_boundary_v23
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_center_v24
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_billing_subscription_lifecycle
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_user_e2e_safety
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_v2_readiness.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_user_e2e.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_billing_lifecycle.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_query_quality_v4.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_functional_v5.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_usability_v6.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_speed_v7.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_resilience_v8.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_source_health_v9.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_persistent_market_cache_v10.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_source_ops_v11.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_prewarm_console_v12.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_recovery_console_v13.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_real_use_loop_v14.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_user_query_loop_v15.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_browser_user_loop_v16.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_watchlist_v17.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_watchlist_board_v18.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_workspace_v19.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_public_entry_v20.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_public_user_flow_v21.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_refresh_v22.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_snapshot_boundary_v23.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_center_v24.py
```

Rollback note: if a verifier is rolled back, also roll back its tests and `.gitignore` exception if the verifier should no longer be visible.

Files:

- `apps/dsa-web/playwright.config.ts`
- `apps/dsa-web/e2e/platform-user-e2e.spec.ts`
- `tests/test_api_health.py`
- `tests/test_analysis_api_contract.py`
- `tests/test_analysis_history.py`
- `tests/test_basic_query_no_ai.py`
- `tests/test_billing_api.py`
- `tests/test_billing_sandbox_flow.py`
- `tests/test_billing_subscription_lifecycle.py`
- `tests/test_local_model_router.py`
- `tests/test_local_v1_operability.py`
- `tests/test_market_data_cache.py`
- `tests/test_platform_accounts.py`
- `tests/test_platform_ai_feature_quota.py`
- `tests/test_platform_api.py`
- `tests/test_platform_api_keys_product.py`
- `tests/test_platform_audit.py`
- `tests/test_platform_feature_policy.py`
- `tests/test_platform_query_quality_v4.py`
- `tests/test_platform_local_functional_v5.py`
- `tests/test_platform_local_usability_v6.py`
- `tests/test_platform_local_query_speed_v7.py`
- `tests/test_platform_local_query_resilience_v8.py`
- `tests/test_platform_local_market_source_health_v9.py`
- `tests/test_platform_local_persistent_market_cache_v10.py`
- `tests/test_platform_local_market_source_ops_v11.py`
- `tests/test_platform_local_market_prewarm_console_v12.py`
- `tests/test_platform_local_market_recovery_console_v13.py`
- `tests/test_platform_local_real_use_loop_v14.py`
- `tests/test_platform_local_user_query_loop_v15.py`
- `tests/test_platform_local_browser_user_loop_v16.py`
- `tests/test_platform_local_watchlist_v17.py`
- `tests/test_platform_local_watchlist_v17_verifier.py`
- `tests/test_platform_local_watchlist_board_v18.py`
- `tests/test_platform_local_query_workspace_v19.py`
- `tests/test_platform_local_public_entry_v20.py`
- `tests/test_platform_local_public_user_flow_v21.py`
- `tests/test_platform_local_market_refresh_v22.py`
- `tests/test_platform_local_history_snapshot_boundary_v23.py`
- `tests/test_platform_local_history_center_v24.py`
- `tests/test_platform_local_history_center_v25.py`
- `tests/test_platform_local_history_center_v26.py`
- `tests/test_platform_local_history_export_v27.py`
- `tests/test_platform_local_history_detail_v30.py`
- `tests/test_platform_security_boundaries.py`
- `tests/test_platform_user_journey.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_platform_user_e2e_safety.py`
- `scripts/cleanup_platform_e2e_data.py`
- `scripts/verify_local_v1_operability.py`
- `scripts/verify_platform_v2_readiness.py`
- `scripts/verify_platform_release_candidate_package.py`
- `scripts/verify_platform_user_e2e.py`
- `scripts/verify_platform_billing_lifecycle.py`
- `scripts/verify_platform_query_quality_v4.py`
- `scripts/verify_platform_local_functional_v5.py`
- `scripts/verify_platform_local_usability_v6.py`
- `scripts/verify_platform_local_query_speed_v7.py`
- `scripts/verify_platform_local_query_resilience_v8.py`
- `scripts/verify_platform_local_market_source_health_v9.py`
- `scripts/verify_platform_local_persistent_market_cache_v10.py`
- `scripts/verify_platform_local_market_source_ops_v11.py`
- `scripts/verify_platform_local_market_prewarm_console_v12.py`
- `scripts/verify_platform_local_market_recovery_console_v13.py`
- `scripts/verify_platform_local_real_use_loop_v14.py`
- `scripts/verify_platform_local_user_query_loop_v15.py`
- `scripts/verify_platform_local_browser_user_loop_v16.py`
- `scripts/verify_platform_local_watchlist_v17.py`
- `scripts/verify_platform_local_watchlist_board_v18.py`
- `scripts/verify_platform_local_query_workspace_v19.py`
- `scripts/verify_platform_local_public_entry_v20.py`
- `scripts/verify_platform_local_public_user_flow_v21.py`
- `scripts/verify_platform_local_market_refresh_v22.py`
- `scripts/verify_platform_local_history_snapshot_boundary_v23.py`
- `scripts/verify_platform_local_history_center_v24.py`
- `scripts/verify_platform_local_history_center_v25.py`
- `scripts/verify_platform_local_history_center_v26.py`
- `scripts/verify_platform_local_history_export_v27.py`
- `scripts/verify_platform_local_history_detail_v30.py`

Review note:

- `scripts/verify_local_v1_operability.py --auto-smoke-user` is opt-in local-only smoke support. It registers only `e2e+local-smoke...` users through the running local API, does not print generated passwords, and does not delete data.
- `scripts/verify_platform_local_functional_v5.py` is the Local Functional V5 aggregate gate. It registers only `e2e+local-v5...` smoke users through the running local API, reports optional live market data as degraded when unstable, does not print generated passwords, and prints `DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK` only when required local checks pass. Sandbox billing in this gate is not real payment.
- `scripts/verify_platform_local_usability_v6.py` is the Local Usability V6 aggregate gate. It fails if V5 required checks are failed or degraded, including stale live 8018 account/billing routes after login, and prints `DSA_PLATFORM_LOCAL_USABILITY_V6_OK` only when required local checks pass. The optional multi-market quick smoke checks A-share, US, HK, and crypto no-AI routes; stale or slow market data remains diagnostic only.
- `scripts/verify_platform_local_query_speed_v7.py` is the Local Query Speed V7 gate. It proves the no-AI quick snapshot contract includes timing, cache, source, freshness, and performance diagnostics, and prints `DSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK` only when required local checks pass. Optional live source slowness remains diagnostic only.
- `scripts/verify_platform_local_query_resilience_v8.py` is the Local Query Resilience V8 gate. It proves slow quick-query source calls degrade through sanitized timeout/fallback diagnostics instead of blocking or invoking AI, and prints `DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK` only when required local checks pass.
- `scripts/verify_platform_local_market_source_health_v9.py` is the Local Market Source Health V9 gate. It proves repeated source failures enter cooldown, prewarm remains no-AI, diagnostics include source-health state, and prints `DSA_PLATFORM_LOCAL_MARKET_SOURCE_HEALTH_V9_OK` only when required local checks pass.
- `scripts/verify_platform_local_persistent_market_cache_v10.py` is the Local Persistent Market Cache V10 gate. It proves disk-backed cache fallback works, persistent-cache diagnostics are present, no-AI boundaries stay intact, and prints `DSA_PLATFORM_LOCAL_PERSISTENT_MARKET_CACHE_V10_OK` only when required local checks pass.
- `scripts/verify_platform_local_market_source_ops_v11.py` is the Local Market Source Ops V11 gate. It proves source priority, source health, cooldown, latency, cache-mode diagnostics, and no-AI boundaries are exposed through a read-only local endpoint, and prints `DSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK` only when required local checks pass.
- `scripts/verify_platform_local_market_prewarm_console_v12.py` is the Local Market Prewarm Console V12 gate. It proves the AdminPage prewarm control, latest prewarm summary, V11 source-health compatibility, and no-AI prewarm payload boundary, and prints `DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK` only when required local checks pass.
- `scripts/verify_platform_local_market_recovery_console_v13.py` is the Local Market Recovery Console V13 gate. It proves the admin-only recovery API, AdminPage recovery control, selected source-health reset summary, V12 compatibility, and no-AI recovery/prewarm payload boundary, and prints `DSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK` only when required local checks pass.
- `scripts/verify_platform_local_real_use_loop_v14.py` is the Local Real Use Loop V14 gate. It proves the admin-only local functional status API, AdminPage local status panel, V13 compatibility, no-AI status payload boundary, and secret-redaction expectations, and prints `DSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK` only when required local checks pass.
- `scripts/verify_platform_local_user_query_loop_v15.py` is the Local User Query Loop V15 gate. It proves HomePage ordinary-user query guardrails, masked BYOK status, current no-AI snapshot separation from historical reports, V14 compatibility, and no-AI market-lane payload shape, and prints `DSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK` only when required local checks pass.
- `scripts/verify_platform_local_browser_user_loop_v16.py` is the Local Browser User Loop V16 gate. It proves the ordinary-user Playwright browser flow, V15 compatibility, and live-smoke summary shape for A-share, US, HK, and crypto no-AI quick snapshots, and prints `DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK` only when required local checks pass.
- `scripts/verify_platform_local_watchlist_v17.py` is the Local Watchlist V17 gate. It proves private platform-user watchlist behavior, no-AI multi-market refresh summary shape, V16 compatibility, backend tests, and HomePage target tests, and prints `DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK` only when required local checks pass.
- `scripts/verify_platform_local_watchlist_board_v18.py` is the Local Watchlist Board V18 gate. It proves refreshed board rows include no-AI multi-market lane, price, change, freshness, degradation, warning, and row-query behavior, and prints `DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK` only when required local checks pass.
- `scripts/verify_platform_local_query_workspace_v19.py` is the Local Query Workspace V19 gate. It proves current snapshot, private watchlist, separate history, and AI analysis states remain visibly separated without creating a new AI path, and prints `DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK` only when required local checks pass.
- `scripts/verify_platform_local_public_entry_v20.py` is the Local Public Entry V20 gate. It proves ordinary platform-user entry routes remain reachable without an admin cookie while admin/settings remain admin-only, and prints `DSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_OK` only when required local checks pass.
- `scripts/verify_platform_local_public_user_flow_v21.py` is the Local Public User Flow V21 gate. It proves ordinary-user local register/login, account summary, four-market no-AI quick route, private watchlist refresh, and ordinary-user admin 403 boundaries, and prints `DSA_PLATFORM_LOCAL_PUBLIC_USER_FLOW_V21_OK` only when required local checks pass.
- `scripts/verify_platform_local_market_refresh_v22.py` is the Local Market Refresh V22 gate. It proves `refresh=true` bypasses snapshot cache, keeps quick refresh no-AI, renders refresh diagnostics, and prints `DSA_PLATFORM_LOCAL_MARKET_REFRESH_V22_OK` only when required local checks pass.
- `scripts/verify_platform_local_history_snapshot_boundary_v23.py` is the Local History Snapshot Boundary V23 gate. It proves historical AI reports remain visibly separate from current quote data and current quote refresh remains no-AI.
- `scripts/verify_platform_local_history_center_v24.py` is the Local History Center V24 gate. It proves History Center filters, session-only current-quote refresh markers, and no-AI refresh behavior.
- `scripts/verify_platform_local_history_center_v25.py` is the Local History Center V25 gate. It proves backend history filtering, stable pagination, persistent user-scoped no-AI refresh markers, and marker API guards.
- `scripts/verify_platform_local_history_center_v26.py` is the Local History Center V26 gate. It proves validated filter persistence, restored backend-filter requests, and backend total count display.
- `scripts/verify_platform_local_history_export_v27.py` is the Local History Export V27 gate. It proves selected history export stays owner-scoped, no-AI, secret-redacted, and local-only.
- `scripts/verify_platform_local_history_detail_v30.py` is the Local History Detail V30 gate. It proves report detail search, section jumps, same-stock timeline, owner-scoped history reuse, and no-AI navigation behavior.

## Slice: docs-and-config

Purpose: operator-readable V1/V2 evidence, launch-readiness notes, production-evaluation env template, legal/privacy draft, handoff, review slices, and release manifest.

Risk: medium. Bad docs can imply public launch approval, hide no-go items, or accidentally carry real secrets.

Suggested verification:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_v2_readiness.py
git diff --check
```

Rollback note: docs/config can roll back separately from code, but do not remove V1/V2 evidence files if they are needed for handoff.

Files:

- `docs/superpowers/plans/2026-07-01-dsa-platform-monetization.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v5-operability.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v6-usability.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v7-query-speed.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v8-query-resilience.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v9-market-source-health.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v10-persistent-market-cache.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v11-market-source-ops.md`
- `docs/superpowers/plans/2026-07-02-dsa-local-v12-market-prewarm-console.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v14-real-use-loop.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v15-user-query-loop.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v16-browser-user-loop.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v17-user-watchlist.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v18-watchlist-board.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v19-query-workspace.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v21-public-user-flow.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v22-market-refresh.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v23-history-snapshot-boundary.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v24-history-center.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v25-history-center-persistence.md`
- `docs/superpowers/plans/2026-07-03-dsa-local-v26-history-center-usability.md`
- `docs/superpowers/plans/2026-07-04-dsa-local-v27-history-export.md`
- `docs/superpowers/plans/2026-07-04-dsa-local-v30-history-detail.md`
- `docs/superpowers/platform-legal-copy-draft.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-local-v1-operability.md`
- `docs/superpowers/platform-local-v1-security-checklist.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-production-env.example`
- `docs/superpowers/platform-v2-handoff-status.md`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

## Slice: build-and-ignore-impact

Purpose: keep verifier files visible and document generated build output impact.

Risk: low, but a bad ignore rule can hide required verifier files or accidentally expose local artifacts.

Suggested verification:

```powershell
git check-ignore -q scripts\verify_local_v1_operability.py; if ($LASTEXITCODE -eq 0) { throw "local verifier is ignored" }
git check-ignore -q scripts\verify_platform_v2_readiness.py; if ($LASTEXITCODE -eq 0) { throw "v2 verifier is ignored" }
git check-ignore -q scripts\verify_platform_release_candidate_package.py; if ($LASTEXITCODE -eq 0) { throw "release package verifier is ignored" }
git check-ignore -q scripts\verify_platform_user_e2e.py; if ($LASTEXITCODE -eq 0) { throw "platform user E2E verifier is ignored" }
git check-ignore -q scripts\verify_platform_billing_lifecycle.py; if ($LASTEXITCODE -eq 0) { throw "platform billing lifecycle verifier is ignored" }
git check-ignore -q scripts\verify_platform_query_quality_v4.py; if ($LASTEXITCODE -eq 0) { throw "platform query quality verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_functional_v5.py; if ($LASTEXITCODE -eq 0) { throw "platform local functional V5 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_usability_v6.py; if ($LASTEXITCODE -eq 0) { throw "platform local usability V6 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_query_speed_v7.py; if ($LASTEXITCODE -eq 0) { throw "platform local query speed V7 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_query_resilience_v8.py; if ($LASTEXITCODE -eq 0) { throw "platform local query resilience V8 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_market_source_health_v9.py; if ($LASTEXITCODE -eq 0) { throw "platform local market source health V9 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_persistent_market_cache_v10.py; if ($LASTEXITCODE -eq 0) { throw "platform local persistent market cache V10 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_market_source_ops_v11.py; if ($LASTEXITCODE -eq 0) { throw "platform local market source ops V11 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_market_prewarm_console_v12.py; if ($LASTEXITCODE -eq 0) { throw "platform local market prewarm console V12 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_market_recovery_console_v13.py; if ($LASTEXITCODE -eq 0) { throw "platform local market recovery console V13 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_real_use_loop_v14.py; if ($LASTEXITCODE -eq 0) { throw "platform local real use loop V14 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_user_query_loop_v15.py; if ($LASTEXITCODE -eq 0) { throw "platform local user query loop V15 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_browser_user_loop_v16.py; if ($LASTEXITCODE -eq 0) { throw "platform local browser user loop V16 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_watchlist_v17.py; if ($LASTEXITCODE -eq 0) { throw "platform local watchlist V17 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_watchlist_board_v18.py; if ($LASTEXITCODE -eq 0) { throw "platform local watchlist board V18 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_query_workspace_v19.py; if ($LASTEXITCODE -eq 0) { throw "platform local query workspace V19 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_public_entry_v20.py; if ($LASTEXITCODE -eq 0) { throw "platform local public entry V20 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_public_user_flow_v21.py; if ($LASTEXITCODE -eq 0) { throw "platform local public user flow V21 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_market_refresh_v22.py; if ($LASTEXITCODE -eq 0) { throw "platform local market refresh V22 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_history_snapshot_boundary_v23.py; if ($LASTEXITCODE -eq 0) { throw "platform local history snapshot boundary V23 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_history_center_v24.py; if ($LASTEXITCODE -eq 0) { throw "platform local history center V24 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_history_center_v25.py; if ($LASTEXITCODE -eq 0) { throw "platform local history center V25 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_history_center_v26.py; if ($LASTEXITCODE -eq 0) { throw "platform local history center V26 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_history_export_v27.py; if ($LASTEXITCODE -eq 0) { throw "platform local history export V27 verifier is ignored" }
git check-ignore -q scripts\verify_platform_local_history_detail_v30.py; if ($LASTEXITCODE -eq 0) { throw "platform local history detail V30 verifier is ignored" }
git diff --check
```

Rollback note: if `.gitignore` is rolled back, rerun `scripts\verify_platform_release_candidate_package.py` to ensure required verifier scripts are still visible.

Files:

- `.gitignore`

Generated output note:

- `static/` is build output from `npm run build`; it is ignored and should not be deleted as cleanup.
- `scripts/verify_platform_local_query_speed_v7.py` must stay visible for local query-speed diagnostics review.
- `scripts/verify_platform_local_query_resilience_v8.py` must stay visible for local query-resilience diagnostics review.
- `scripts/verify_platform_local_market_source_health_v9.py` must stay visible for local market-source health diagnostics review.
- `scripts/verify_platform_local_persistent_market_cache_v10.py` must stay visible for local persistent-cache diagnostics review.
- `scripts/verify_platform_local_market_source_ops_v11.py` must stay visible for local market-source ops diagnostics review.
- `scripts/verify_platform_local_market_prewarm_console_v12.py` must stay visible for local market prewarm console review.
- `scripts/verify_platform_local_market_recovery_console_v13.py` must stay visible for local market recovery console review.
- `scripts/verify_platform_local_real_use_loop_v14.py` must stay visible for local real-use loop review.
- `scripts/verify_platform_local_user_query_loop_v15.py` must stay visible for local user query loop review.
- `scripts/verify_platform_local_browser_user_loop_v16.py` must stay visible for local browser user loop review.
- `scripts/verify_platform_local_watchlist_v17.py` must stay visible for local watchlist review.
- `scripts/verify_platform_local_watchlist_board_v18.py` must stay visible for local watchlist board review.
- `scripts/verify_platform_local_query_workspace_v19.py` must stay visible for local query workspace review.
- `scripts/verify_platform_local_public_entry_v20.py` must stay visible for local public entry review.
- `scripts/verify_platform_local_public_user_flow_v21.py` must stay visible for local public user flow review.
- `scripts/verify_platform_local_market_refresh_v22.py` must stay visible for local market refresh review.
- `scripts/verify_platform_local_history_snapshot_boundary_v23.py` must stay visible for local history/current snapshot boundary review.
- `scripts/verify_platform_local_history_center_v24.py` must stay visible for local history center review.
- `scripts/verify_platform_local_history_center_v25.py` must stay visible for backend-filtered local history center persistence review.
- `scripts/verify_platform_local_history_center_v26.py` must stay visible for local history center usability review.
- `scripts/verify_platform_local_history_export_v27.py` must stay visible for local history export review.
- `scripts/verify_platform_local_history_detail_v30.py` must stay visible for local history detail tools review.

## Slice: manual-confirmation

Purpose: dependency or potentially cross-cutting changes that need explicit human review before grouping with a code slice.

Risk: medium. Dependency changes can affect reproducibility and packaging beyond the platform feature.

Suggested verification:

```powershell
git diff -- requirements.txt
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_api_keys_product tests.test_platform_accounts
```

Rollback note: do not revert `requirements.txt` without confirming whether API key encryption or platform account security depends on it.

Files:

- `requirements.txt`

## Human Decisions Before Public Launch

- Real payment provider, merchant account, webhook reconciliation, refunds, invoices, taxes, and rollback.
- Production hosting, real domain, HTTPS certificates, WAF/CDN, monitoring, alerting, and incident response.
- Email/SMS verification, password reset, account recovery, external login, or SSO.
- Legal terms, privacy policy, retention/deletion/export policy, and final risk disclaimer.
- Commercial plan names, quota numbers, paid limits, and pricing.

This package can enter human review and possible commit slicing after verification, but it is not public-launch approval.

## V28 Local History State Manifest Addendum

Status: local-only, no public launch approval.

New/updated files:

- `api/v1/endpoints/history.py`
- `api/v1/schemas/history.py`
- `src/storage.py`
- `src/services/history_service.py`
- `apps/dsa-web/src/api/history.ts`
- `apps/dsa-web/src/types/analysis.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `apps/dsa-web/src/components/history/HistoryList.tsx`
- `apps/dsa-web/src/components/history/HistoryListItem.tsx`
- `tests/test_platform_local_history_state_v28.py`
- `scripts/verify_platform_local_history_state_v28.py`
- `docs/superpowers/plans/2026-07-04-dsa-local-v28-history-state.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_HISTORY_STATE_V28_OK`

Review boundary:

- `analysis_history_user_states` is a side table for favorite, important, archived, read, and note.
- State APIs are owner-scoped and no-AI.
- Batch archive/restore must not delete history reports.
- Keep `scripts/verify_platform_local_history_state_v28.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V29 Local History Operations Manifest Addendum

Status: local-only, no public launch approval.

New/updated files:

- `api/v1/endpoints/history.py`
- `src/storage.py`
- `src/services/history_service.py`
- `apps/dsa-web/src/api/history.ts`
- `apps/dsa-web/src/types/analysis.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `apps/dsa-web/src/components/history/HistoryList.tsx`
- `tests/test_platform_local_history_ops_v29.py`
- `scripts/verify_platform_local_history_ops_v29.py`
- `docs/superpowers/plans/2026-07-04-dsa-local-v29-history-ops.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_HISTORY_OPS_V29_OK`

Review boundary:

- Note search is owner-scoped and no-AI.
- History Center defaults to active records while preserving archived records.
- Batch important/read must not delete history reports or consume AI quota.
- Date groups are display-only.
- Keep `scripts/verify_platform_local_history_ops_v29.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V30 Local History Detail Manifest Addendum

Status: local-only, no public launch approval.

New/updated files:

- `api/v1/endpoints/history.py`
- `src/services/history_service.py`
- `apps/dsa-web/src/api/history.ts`
- `apps/dsa-web/src/components/report/ReportSummary.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `tests/test_platform_local_history_detail_v30.py`
- `scripts/verify_platform_local_history_detail_v30.py`
- `docs/superpowers/plans/2026-07-04-dsa-local-v30-history-detail.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK`

Review boundary:

- Report detail search, search match navigation, section jumps, and same-stock timeline are local-only no-AI read tools.
- Same-stock timeline reuses existing owner-scoped history list records and must not add a separate timeline endpoint.
- `ReportSummary` section anchors are display-only and must not rewrite historical report content.
- Keep `scripts/verify_platform_local_history_detail_v30.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V48 Production Readiness Manifest Addendum

Status: local-only production preflight, no public launch approval.

New/updated files:

- `api/v1/endpoints/platform.py`
- `src/services/production_readiness.py`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/pages/AdminPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`
- `tests/test_platform_production_readiness_v48.py`
- `scripts/verify_platform_production_readiness_v48.py`
- `docs/superpowers/plans/2026-07-05-dsa-production-readiness-v48.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_PRODUCTION_READINESS_V48_OK`

Review boundary:

- Production readiness is an admin-only local preflight, not a public launch switch.
- `launch_decision` must remain blocked until real payment, production domain, HTTPS/WAF, data-source commercial license, legal terms, privacy policy, monitoring, and backup/restore evidence are approved.
- The endpoint and verifier must not call AI, consume model quota, fetch live market data, or expose real API keys.
- Keep `scripts/verify_platform_production_readiness_v48.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, do not treat this as production deployment, and do not treat this as investment advice.

## V49 Billing Provider Boundary Manifest Addendum

Status: local-only payment-provider boundary, no real payment approval.

New/updated files:

- `api/v1/endpoints/billing.py`
- `src/billing/payment_provider.py`
- `src/services/production_readiness.py`
- `tests/test_billing_provider_boundary_v49.py`
- `scripts/verify_platform_billing_provider_boundary_v49.py`
- `docs/superpowers/plans/2026-07-05-dsa-billing-provider-boundary-v49.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK`

Review boundary:

- Billing provider readiness must be sanitized and must not expose secret values from env.
- `BILLING_PROVIDER=stripe` is only a recognized boundary in this local stage, not a live Stripe integration.
- Missing real-provider config must fail closed as `billing_provider_not_ready`.
- Complete placeholder config must still fail closed as `billing_provider_adapter_not_implemented` until a real adapter is deliberately built and reviewed.
- Keep `scripts/verify_platform_billing_provider_boundary_v49.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, do not treat this as production deployment, and do not treat this as investment advice.

## V50 Production Env Gates Manifest Addendum

Status: local-only production configuration hardening, no public launch approval.

New/updated files:

- `docs/superpowers/platform-production-env.example`
- `scripts/verify_platform_v2_readiness.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_platform_production_env_gates_v50.py`
- `scripts/verify_platform_production_env_gates_v50.py`
- `docs/superpowers/plans/2026-07-05-dsa-production-env-gates-v50.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK`

Review boundary:

- Production env defaults must remain launch-blocking and secret-free.
- Real payment, production infrastructure, data-source license, legal/privacy, monitoring, and backup gates are explicit `false` until humans approve evidence.
- Stripe-like provider placeholders are blank and must not be treated as working credentials.
- Keep `scripts/verify_platform_production_env_gates_v50.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, do not treat this as production deployment, and do not treat this as investment advice.

## V51 Backup Restore Drill Manifest Addendum

Status: local-only backup/restore drill tooling, no production backup approval.

New/updated files:

- `src/services/platform_backup.py`
- `scripts/run_platform_backup_restore_dry_run.py`
- `tests/test_platform_backup_restore_drill_v51.py`
- `scripts/verify_platform_backup_restore_drill_v51.py`
- `docs/superpowers/plans/2026-07-05-dsa-backup-restore-drill-v51.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK`

Review boundary:

- Backup/restore drill uses temporary databases in verifier mode and must not delete or overwrite live data.
- Operational runner creates separate backup/restored copies and reports integrity, hash, row-count, `source_unchanged`, `destructive=false`, and `ai_used=false`.
- Production/staging restore approval is still a human gate before public launch.
- Keep `scripts/verify_platform_backup_restore_drill_v51.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, do not treat this as production deployment, and do not treat this as investment advice.

## V52 Ops Health Manifest Addendum

Status: local-only operations health status, no production monitoring approval.

New/updated files:

- `api/v1/endpoints/platform.py`
- `src/services/platform_ops_health.py`
- `tests/test_platform_ops_health_v52.py`
- `scripts/verify_platform_ops_health_v52.py`
- `docs/superpowers/plans/2026-07-05-dsa-ops-health-v52.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-v2-launch-readiness.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_OPS_HEALTH_V52_OK`

Review boundary:

- Ops health is admin-only and read-only.
- Payloads must not expose database absolute paths, real API keys, webhook secrets, or tokens.
- This is not production monitoring, alerting, incident response, WAF/CDN, or public-launch approval.
- Keep `scripts/verify_platform_ops_health_v52.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, do not treat this as production deployment, and do not treat this as investment advice.

## V53 Ops Health Panel Manifest Addendum

Status: local-only admin UI wiring, no production monitoring approval.

New/updated files:

- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/pages/AdminPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`
- `scripts/verify_platform_ops_health_panel_v53.py`
- `docs/superpowers/plans/2026-07-05-dsa-ops-health-panel-v53.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_OPS_HEALTH_PANEL_V53_OK`

Review boundary:

- AdminPage ops health panel is read-only and must not trigger AI, payment processing, or market-data fetches.
- It must not expose API keys, webhook secrets, tokens, or database absolute paths.
- This is not production monitoring, alerting, WAF/CDN, incident response, or public-launch approval.
- Keep `scripts/verify_platform_ops_health_panel_v53.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V54 Local User Acceptance Manifest Addendum

Status: local-only anonymous/free query acceptance, no production launch approval.

New/updated files:

- `src/services/basic_query_service.py`
- `tests/test_basic_query_no_ai.py`
- `tests/test_platform_local_user_acceptance_v54.py`
- `scripts/verify_platform_local_user_acceptance_v54.py`
- `docs/superpowers/plans/2026-07-06-dsa-v54-local-user-acceptance.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_USER_ACCEPTANCE_V54_OK`

Review boundary:

- Anonymous users can query free no-AI snapshots without login.
- Free reports should show rich deterministic sections before upselling quick/deep AI analysis.
- HK realtime quote failures should degrade to latest historical close for display, with an explicit warning and no AI call.
- Keep `scripts/verify_platform_local_user_acceptance_v54.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V55 Local Product Experience Manifest Addendum

Status: local-only guest-first product experience, no production launch approval.

New/updated files:

- `.gitignore`
- `api/v1/schemas/basic_query.py`
- `src/services/basic_query_service.py`
- `tests/test_basic_query_no_ai.py`
- `tests/test_platform_local_product_experience_v55.py`
- `scripts/verify_platform_local_product_experience_v55.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_PRODUCT_EXPERIENCE_V55_OK`

Review boundary:

- Anonymous users can query first; login and registration are helpful prompts, not blockers.
- The free report includes `retention_brief`, `basic-query-retention-brief`, and `guest-conversion-guide` while keeping no-AI cost control.
- Keep `scripts/verify_platform_local_product_experience_v55.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V56 Local User Retention Manifest Addendum

Status: local-only ordinary-user retention loop, no production launch approval.

New/updated files:

- `api/v1/schemas/platform.py`
- `api/v1/endpoints/platform.py`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `apps/dsa-web/e2e/platform-user-e2e.spec.ts`
- `tests/test_platform_local_user_retention_v56.py`
- `scripts/verify_platform_local_user_retention_v56.py`
- `docs/superpowers/plans/2026-07-06-dsa-v56-user-retention-loop.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK`

Suggested review/commit position:

- After V55 guest-first product experience and before broader production-readiness or payment/provider work.

Rollback notes:

- Reverting this slice removes the snapshot-to-history endpoint, HomePage retention actions, V56 E2E path, and V56 verifier without touching existing saved history tables or previous V55 no-AI snapshot behavior.

Review boundary:

- Snapshot saves must remain login-required, no-AI only, and scoped to `platform_user_id`.
- Watchlist and history actions must not expose plaintext API keys or global platform secrets.
- Playwright coverage is mock-backed; it is not proof of public production deployment.
- Keep `scripts/verify_platform_local_user_retention_v56.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V57 Local News And K-Line Forecast Lab Manifest Addendum

Status: local-only free-query product enrichment, no production launch approval.

New/updated files:

- `api/v1/schemas/basic_query.py`
- `src/services/basic_query_service.py`
- `tests/test_basic_query_no_ai.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `tests/test_platform_local_news_kline_v57.py`
- `scripts/verify_platform_local_news_kline_v57.py`
- `docs/superpowers/plans/2026-07-06-dsa-v57-news-kline-forecast-lab.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `.gitignore`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Acceptance marker:

- `DSA_PLATFORM_LOCAL_NEWS_KLINE_V57_OK`

Suggested review/commit position:

- After V56 user retention loop and before production Kronos hosting, market-data licensing, or production payment work.

Rollback notes:

- Reverting this slice removes the `news_center` and `kline_forecast` payloads, HomePage V57 panels, V57 verifier, and V57 docs. Existing quick snapshot, retention brief, save-history, watchlist, and billing sandbox behavior should remain unaffected.

Review boundary:

- `news_center` is deterministic no-AI content and must not call public search or paid APIs.
- `kline_forecast` is a Kronos-ready preview only; `kronos_model_used=false` until a real adapter and approval gate exist.
- Keep `scripts/verify_platform_local_news_kline_v57.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V58 Kronos Sandbox Manifest Addendum

Status: local-only Kronos adapter sandbox, no production launch approval and no hosted model SLA.

New/updated files:

- `.gitignore`
- `api/middlewares/auth.py`
- `api/v1/endpoints/stocks.py`
- `api/v1/schemas/basic_query.py`
- `src/services/kronos_forecast_service.py`
- `tests/test_kronos_forecast_service_v58.py`
- `tests/test_kronos_forecast_api_v58.py`
- `tests/test_platform_kronos_sandbox_v58.py`
- `scripts/verify_platform_kronos_sandbox_v58.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `docs/superpowers/plans/2026-07-06-dsa-v58-kronos-sandbox.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Acceptance marker:

- `DSA_PLATFORM_KRONOS_SANDBOX_V58_OK`

Suggested review/commit position:

- After V57 local news/K-line forecast lab and before production Kronos hosting, Hugging Face model download policy, GPU sizing, paid entitlement, or production market-data licensing work.

Rollback notes:

- Reverting this slice removes the standalone `kronos-forecast` endpoint, local Kronos sandbox service, HomePage live Kronos check panel, V58 verifier, and V58 docs. Existing V57 no-AI `kline_forecast` preview remains as long as V57 is kept.

Review boundary:

- Public fallback must not invoke AI, public search, paid APIs, or BYOK secrets.
- `require_model=true` must not be available to anonymous/free users.
- Current local environment may legitimately return `model_ready` when started with the local Kronos runtime flags, or `model_unavailable` / `model_disabled` when dependencies or flags are absent; either state must be displayed honestly, not hidden.
- Keep `scripts/verify_platform_kronos_sandbox_v58.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V59 A-Stock-Data POC Manifest Addendum

Status: local-only A-share enrichment POC, no production launch approval, no real payment, and no market-data licensing approval.

New/updated files:

- `.gitignore`
- `api/v1/schemas/basic_query.py`
- `src/services/basic_query_service.py`
- `src/services/a_share_enrichment_service.py`
- `tests/test_basic_query_no_ai.py`
- `tests/test_a_share_enrichment_service.py`
- `tests/test_platform_a_stock_data_poc_v59.py`
- `scripts/verify_platform_a_stock_data_poc_v59.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `docs/superpowers/plans/2026-07-07-dsa-v59-a-stock-data-poc.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_A_STOCK_DATA_POC_V59_OK`

Suggested review/commit position:

- After V58 Kronos sandbox and before any production data-source licensing, public news/search expansion, or paid A-share data-source integration.

Rollback notes:

- Reverting this slice removes the `a_share_enrichment` payload, local A-share enrichment adapter, HomePage A-share enrichment panel, V59 verifier, and V59 docs. Existing quick snapshot, V57 news center, and V58 Kronos sandbox should remain unaffected if their slices are kept.

Review boundary:

- A-share enrichment quick mode must not invoke AI, public search, paid APIs, BYOK secrets, or production data-source credentials.
- Adapter source failures must remain visible degraded states, not hidden successes.
- Keep `scripts/verify_platform_a_stock_data_poc_v59.py` visible despite the broad `verify_*.py` ignore rule.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V60 A-Stock-Data Source Manifest Addendum

Status: local-only configurable source adapter for the locally cloned `simonlin1212/a-stock-data` repository. It does not approve production deployment, real payment, production secrets, or market-data redistribution.

New/updated files:

- `.gitignore`
- `api/v1/schemas/basic_query.py`
- `src/services/a_share_enrichment_service.py`
- `tests/test_a_share_enrichment_service.py`
- `scripts/verify_platform_a_stock_data_v60.py`
- `tests/test_platform_a_stock_data_v60.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `apps/dsa-web/src/api/stocks.ts`
- `docs/superpowers/plans/2026-07-07-dsa-v60-a-stock-data-source.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_A_STOCK_DATA_V60_OK`

Suggested review/commit position:

- After V59 A-share enrichment POC and before any live paid data-source, public news/search, or production data licensing work.

Rollback note:

- Reverting this slice removes `A_STOCK_DATA_SOURCE_MODE=a_stock_data`, source diagnostics, cache/rate-limit adapter behavior, and the V60 verifier. The V59 local quick-reference A-share enrichment panel can remain if its slice is kept.

Review boundary:

- External calls are disabled by default.
- Cache and rate limit are mandatory for any source adapter call path.
- Diagnostics must remain secret-safe.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V61 A-Stock-Data UI Manifest Addendum

Status: local-only HomePage source-control layer for the V60 A-share adapter. It does not approve production deployment, real payment, production secrets, or market-data redistribution.

New/updated files:

- `.gitignore`
- `api/v1/endpoints/stocks.py`
- `tests/test_basic_query_no_ai.py`
- `scripts/verify_platform_a_stock_data_ui_v61.py`
- `tests/test_platform_a_stock_data_ui_v61.py`
- `scripts/verify_platform_release_candidate_package.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `docs/superpowers/plans/2026-07-07-dsa-v61-a-stock-data-ui.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_A_STOCK_DATA_UI_V61_OK`

Suggested review/commit position:

- After V60 source adapter and before any live paid A-share data-source, public news/search expansion, or production data licensing work.

Rollback note:

- Reverting this slice removes the HomePage source selector, API query option, V61 verifier, and V61 docs. The V60 backend adapter remains available through configuration if its slice is kept.

Review boundary:

- Probe queries remain no-AI and no-public-search.
- UI diagnostics must remain secret-safe.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V62 A-Stock-Data Useful Data Manifest Addendum

Status: local-only useful-data upgrade for the A-share `a-stock-data` adapter. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `src/services/a_share_enrichment_service.py`
- `tests/test_a_share_enrichment_service.py`
- `scripts/verify_platform_a_stock_data_useful_v62.py`
- `tests/test_platform_a_stock_data_useful_v62.py`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-07-dsa-v62-a-stock-data-useful.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK`

Suggested review/commit position:

- After V61 A-stock-data UI source control and before any paid data-source, production data licensing, or public deployment work.

Rollback note:

- Reverting this slice removes the public-source parser mapping, checked degraded channel copy, Shanghai CNINFO `gssh0{code}` fallback, common A-share sector fallback tags, the `a_stock_data` 2.5s default timeout, A-share default source-mode preference, V62 verifier, and V62 docs. V59/V60/V61 remain available if their slices are kept.

Review boundary:

- No AI calls and no public search.
- Empty or failed public-source channels must be explicit degraded cards.
- Non-A-share inputs must not be routed through A-share source mode.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V63 A-Stock-Data Experience Manifest Addendum

Status: local-only experience upgrade for the A-share enrichment panel. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `src/services/a_share_enrichment_service.py`
- `tests/test_a_share_enrichment_service.py`
- `api/v1/schemas/basic_query.py`
- `tests/test_basic_query_no_ai.py`
- `scripts/verify_platform_a_stock_data_experience_v63.py`
- `tests/test_platform_a_stock_data_experience_v63.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `docs/superpowers/plans/2026-07-08-dsa-v63-a-stock-data-experience.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_A_STOCK_DATA_EXPERIENCE_V63_OK`

Suggested review/commit position:

- After V62 useful-data adapter and before any paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes `reader_summary`, the HomePage first-read summary block, V63 verifier, and V63 docs. V62 data channels remain available if their slice is kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- The summary must explain checked-but-empty/degraded channels without hiding raw channel cards.
- Premium copy should describe a data-channel upgrade, not separate visible features: free and premium show the same modules, while premium/API modes use platform API, user API, approved feeds, or local models for fresher and deeper output.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V64 A-Stock-Data Details Manifest Addendum

Status: local-only usability/data-density upgrade for the A-share enrichment panel. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `api/v1/schemas/basic_query.py`
- `src/services/a_share_enrichment_service.py`
- `tests/test_a_share_enrichment_service.py`
- `tests/test_basic_query_no_ai.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_a_stock_data_details_v64.py`
- `tests/test_platform_a_stock_data_details_v64.py`
- `docs/superpowers/plans/2026-07-08-dsa-v64-a-stock-data-details.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_A_STOCK_DATA_DETAILS_V64_OK`

Suggested review/commit position:

- After V63 first-read summary and before any paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes A-share channel `details`, the HomePage detail rows, V64 verifier, and V64 docs. V63 reader summary and V62 raw channels remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- `details` are compact scan aids and must not hide missing/degraded source state.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V65 Free-Value Experience Manifest Addendum

Status: local-only free user conversion and readability upgrade. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_value_v65.py`
- `tests/test_platform_free_value_v65.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-08-dsa-v65-free-value-experience.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_FREE_VALUE_V65_OK`

Suggested review/commit position:

- After V64 A-share detail-density work and before any paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes the free value summary, collapsed diagnostics default, V65 verifier, and V65 docs. V64 A-share details and earlier no-AI query logic remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- The free summary is a product-value entry layer, not a trade instruction.
- News Center and K-line forecast must remain visible from the free summary as feature entries.
- Diagnostics remain available for support/operator debugging but no longer dominate the free result.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V66 Productized Snapshot Manifest Addendum

Status: local-only productized free-query dashboard upgrade. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_productized_snapshot_v66.py`
- `tests/test_platform_productized_snapshot_v66.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-08-dsa-v66-productized-snapshot.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_OK`

Suggested review/commit position:

- After V65 free-value summary and before any paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes the professional overview block, V66 verifier, and V66 docs. V65 free value summary and earlier no-AI query logic remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- Free and premium show the same visible modules; `免费网络源` and `高级 API 源` are data-channel differences, not separate visible feature walls.
- The professional overview must show trend score, risk level, support/resistance, data channel, and module navigation before deeper details.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V67 Free Research Board Manifest Addendum

Status: local-only free-content quality upgrade. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_research_board_v67.py`
- `tests/test_platform_free_research_board_v67.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-08-dsa-v67-free-research-board.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK`

Suggested review/commit position:

- After V66 productized snapshot and before any paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes the free research board, V67 verifier, and V67 docs. V66 professional overview and V65 free value summary remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- The board must provide concrete scan content across news radar, K-line read, peer/sector context, and risk explanation.
- Free and premium show the same visible research modules; API modes improve freshness, source links, configured feeds, and model depth.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V68 Free Commercial Journey Manifest Addendum

Status: local-only free-result retention upgrade. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_commercial_journey_v68.py`
- `tests/test_platform_free_commercial_journey_v68.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-08-dsa-v68-free-commercial-journey.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_OK`

Suggested review/commit position:

- After V67 free research board and before paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes the commercial journey block, V68 verifier, and V68 docs. V67 free research board, V66 professional overview, and V65 free value summary remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- The journey block must guide the free report reading order and explain the premium/API distinction without hiding core visible modules.
- Guest query remains available; login is only for saved history/watchlist/account state.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V69 Free Data Depth Manifest Addendum

Status: local-only free-result data-value upgrade. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_data_depth_v69.py`
- `tests/test_platform_free_data_depth_v69.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-08-dsa-v69-free-data-depth.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_FREE_DATA_DEPTH_V69_OK`

Suggested review/commit position:

- After V68 free commercial journey and before paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes the free data depth board, V69 verifier, and V69 docs. V68 free commercial journey, V67 free research board, and earlier free query modules remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- The board must show concrete quote, technical, event, peer, and risk fields using existing snapshot data.
- Free and premium show the same visible modules; premium/API modes improve freshness, source links, configured feeds, and model depth.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

## V70 Free Detail Readability Manifest Addendum

Status: local-only free-result readability upgrade. It does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.

New/updated files:

- `.gitignore`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_detail_readability_v70.py`
- `tests/test_platform_free_detail_readability_v70.py`
- `scripts/verify_platform_release_candidate_package.py`
- `src/notification_sender/feishu_sender.py`
- `tests/test_feishu_sender_import_resilience.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-08-dsa-v70-free-detail-readability.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`

Acceptance marker:

- `DSA_PLATFORM_FREE_DETAIL_READABILITY_V70_OK`

Suggested review/commit position:

- After V69 free data depth and before paid data-source, production data licensing, public deployment, or real payment work.

Rollback note:

- Reverting this slice removes the free detail readability layer, V70 verifier, and V70 docs. V69 free data depth and earlier free query modules remain available if those slices are kept.

Review boundary:

- No AI calls and no public search in free quick mode.
- The detail layer must show expandable quote fields, event checklist, peer comparison table, and K-line triggers using existing snapshot data.
- Free and premium show the same visible modules; premium/API modes improve freshness, source links, configured feeds, and model depth.
- Windows local startup must keep working when `lark_oapi` import raises `OSError`; the Feishu App Bot SDK should degrade to unavailable instead of preventing the API from starting.
- Do not commit real API Key, do not connect real payment, and do not treat this as investment advice.

# DSA Platform Review Slices

Date: 2026-07-02

Scope: review slicing for the local V1/V2 platform release-candidate package. This is not a commit plan executed by the agent. Do not run `git add`, `git commit`, or `git push` until a human review owner explicitly approves the slice.

V94 local addendum: A-share history resilience files are included in the existing backend/tests/docs slices:

- `data_provider/base.py`
- `data_provider/efinance_fetcher.py`
- `data_provider/pytdx_fetcher.py`
- `src/services/stock_service.py`
- `tests/test_efinance_history_timeout.py`
- `tests/test_platform_history_resilience_v94.py`
- `docs/superpowers/plans/2026-07-10-dsa-v94-a-share-history-resilience.md`

No-go: real payment disabled, no public deployment, no production secrets, no real API keys in code/docs/logs, and all analysis copy must keep "not investment advice" / "不构成投资建议". Do not commit real API Key.

## Inventory

Baseline before this review package, from `docs/superpowers/platform-v2-handoff-status.md`:

- modified: 32
- untracked: 44
- deleted: 0
- total dirty entries: 76

Expected current release-candidate package after adding the local billing lifecycle gate, Query Quality V4 gate, Local Functional V5 gate, Local Usability V6 gate, Local Query Speed V7 gate, Local Query Resilience V8 gate, Local Market Source Health V9 gate, Local Persistent Market Cache V10 gate, Local Market Source Ops V11 gate, Local Market Prewarm Console V12 gate, Local Market Recovery Console V13 gate, Local Real Use Loop V14 gate, Local User Query Loop V15 gate, Local Browser User Loop V16 gate, Local Watchlist V17 gate, Local Watchlist Board V18 gate, Local Query Workspace V19 gate, Local Public Entry V20 gate, Local Public User Flow V21 gate, Local Market Refresh V22 gate, Local History Snapshot Boundary V23 gate, Local History Center V24/V25 gates, Local History Center Usability V26 gate, Local History Export V27 gate, Local History State V28 gate, Local History Operations V29 gate, and Local History Detail V30 gate:

- modified: 40
- untracked: 147
- deleted: 0
- total dirty entries: 187

Slice counts:

- `backend-platform-foundation`: 37 files
- `frontend-platform-experience`: 29 files
- `tests-and-verifiers`: 82 files
- `docs-and-config`: 37 files
- `build-and-ignore-impact`: 1 tracked dirty file plus ignored `static/` build output
- `manual-confirmation`: 1 file

## backend-platform-foundation

Purpose: platform auth, CSRF, platform user APIs, billing-disabled boundary, quota accounting, history isolation, API key custody, local model routing, and no-AI/basic-query support.

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

Review focus:

- Admin auth and platform user auth stay separate.
- Cookie write endpoints require CSRF when `PLATFORM_CSRF_ENABLED=true`.
- User-owned API keys are encrypted or redacted and never returned as plaintext.
- BYOK/local model lanes use separate quota/capacity accounting.
- Platform write endpoints have local configurable rate-limit coverage for register/login-adjacent flows, API key custody, analysis submit, sandbox checkout, and billing webhook attempts.
- Billing remains disabled unless a real provider, webhook signing, reconciliation, and rollback plan are approved.
- Local sandbox billing lifecycle records checkout sessions, billing events, subscription state, and idempotent `provider_event_id` processing for tests only.
- History/task access remains owner-scoped for platform users and global only for local admin/platform admin.
- V9 source-health cooldown must skip repeatedly failing quick-query sources without invoking AI or leaking raw exceptions.
- V10 persistent market cache must store only market payloads and sanitized source metadata, never headers, tokens, cookies, user identifiers, or API keys.
- V11 market-source ops must stay read-only, list source priority/health/cache mode, and never trigger live market fetches or AI calls.
- V12 market prewarm console must reuse the existing no-AI prewarm endpoint, refresh source health after prewarm, and never consume AI quota.
- V13 market recovery console must reset only selected in-memory source-health cooldown state, optionally prewarm via the no-AI path, require admin access, and never purge user data, reports, API keys, or persistent market cache files.
- V14 local functional status must stay admin-only, read-only, no-AI, secret-free, and local-only while summarizing service, auth, billing, AI/BYOK, market cache, and safety boundaries.
- V15 ordinary-user query loop must keep quick snapshots no-AI, route market lanes clearly, and keep current snapshots separate from historical reports.
- V16 browser user loop must prove the ordinary-user browser flow and live local cookie/no-AI multi-market smoke without crossing into production or real payment.
- V17 platform-user watchlist must stay user-scoped, separate from global `STOCK_LIST`, refresh through no-AI quick snapshots, and avoid consuming AI quota.
- V18 watchlist board must render refreshed rows for A-share, US, HK, and crypto symbols, expose route/degradation/no-AI status, and reuse quick snapshots when a row is queried.
- V19 query workspace must keep current snapshot, private watchlist, historical reports, and AI analysis state visibly separated without creating a new AI path.
- V20 public entry must keep ordinary-user routes open without an admin cookie while protecting admin/settings routes.
- V21 public ordinary-user flow must prove local register/login, account summary, four-market no-AI query, private watchlist refresh, and ordinary-user admin 403 boundaries.
- V22 market refresh must keep cache-first quick snapshots separate from explicit `refresh=true`, bypass snapshot cache only for deterministic no-AI refresh, expose freshness/refresh diagnostics, and never invoke AI.
- V23 history snapshot boundary must keep historical AI reports visibly separate from current quote data and refresh current quote only through the no-AI `snapshot?refresh=true` path.
- V25 history center persistence must keep backend filters owner-scoped, store refresh markers in the side table, reject AI marker writes, and avoid rewriting historical AI report rows.
- V26 history center usability must restore only validated `localStorage` filters, preserve backend-filtered requests, and display backend totals without rewriting old AI reports or creating an AI path.
- V27 history export must keep selected exports owner-scoped, no-AI, secret-redacted, capped, and separate from destructive delete/rewrite operations.

## frontend-platform-experience

Purpose: platform API client wiring, AccountPage, AdminPage, HomePage/basic query UI, navigation, stock API helpers, frontend copy, and related frontend state tests.

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

Review focus:

- AdminPage must not render plaintext API keys, tokens, or secret-like audit metadata.
- AccountPage must only render masked API key state and must not expose plaintext secrets.
- Ordinary platform users should not see the Admin navigation entry after platform session role resolution.
- Failure and empty states must remain usable for admin users.
- Basic query should remain no-AI and clearly separated from paid/deep model workflows.
- Unified quick query now resolves A-share, US equity, HK equity, and crypto spot lanes explicitly; stale or missing quote/history data must return visible degradation warnings without invoking AI.
- V7 quick-query diagnostics should show timing, cache, source, freshness, and performance status without exposing headers, tokens, or API keys.
- V8 quick-query resilience should bound slow source calls, return degraded no-AI snapshots on timeout, and show sanitized timeout/fallback diagnostics.
- V9 prewarm and source-health diagnostics should show cache/source status without exposing raw exceptions, headers, tokens, or API keys.
- V10 persistent-cache diagnostics should show memory/disk state without exposing absolute local paths.
- V11 AdminPage source-health panel should show source priority, cooldown, latency, and cache mode without exposing secrets or raw local paths.
- V12 AdminPage prewarm action should show requested/warmed/degraded/no-AI summary and refresh source health without exposing secrets, raw local paths, or raw provider exceptions.
- V13 AdminPage recovery action should show reset/prewarm/no-AI summary, refresh source health, and avoid exposing secrets, raw local paths, or raw provider exceptions.
- V14 AdminPage local functional status panel should show 8018 readiness, cache, no-AI, BYOK/local model, public-search, and real-payment boundary states without exposing secrets.
- V15 HomePage ordinary-user guardrails should show signed-in user, plan, weekly/free quick quota, masked BYOK status, recommended mode, current no-AI snapshot status, market lane, and history separation without exposing plaintext keys.
- V16 Playwright browser flow should assert ordinary-user account status, masked BYOK state, four-market no-AI quick snapshot guardrails, top-toolbar BYOK quick analysis, sandbox boundary copy, and A/B user isolation.
- V17 HomePage watchlist panel should show private platform-user symbols, add-current action, no-AI refresh summary, degraded count, and route lanes without exposing secrets or implying investment advice.
- V18 HomePage watchlist board should show code, name, market, price, change percent, freshness, route lane, degradation status, warning codes, and no-AI state; row actions must call the quick snapshot path instead of AI analysis.
- V19 HomePage query workspace should show current no-AI snapshot state, private watchlist count, separate history report count, and selected AI/BYOK/local mode without calling AI.
- V32 RouteBoundary should auto-reload exactly once for dynamic-import/chunk-load failures caused by local frontend build swaps, while ordinary route render errors stay on the recoverable error page.
- V20 public entry should not redirect ordinary platform users to the admin login page.
- V21 browser/API flow should keep ordinary-user register/login, account, quick-query, and watchlist operations local-only, no-AI where applicable, and admin-hidden.
- V22 current snapshot refresh should show a manual refresh button, call `snapshot?refresh=true`, render refresh diagnostics, and avoid AI analysis submission.
- V23 historical report view should show `Historical AI report` / `not current quote`, provide a current-quote refresh action, switch to the current snapshot view after refresh, and avoid AI analysis submission.
- V24 History Center should filter loaded history by market/code/report type/time/refresh state and mark `Current quote refreshed` only after a successful no-AI current quote refresh.
- V25 History Center controls should send backend query params through `historyApi.getList`, write refresh markers through `historyApi.markCurrentQuoteRefreshed`, and render persisted `currentQuoteRefreshed` status without exposing secrets.
- V26 History Center should restore validated filter state from `localStorage`, re-apply it through backend filters, and display backend total counts without exposing secrets or changing old AI reports.
- V27 History Center export should download selected local reports as Markdown without invoking AI, exposing secrets, or deleting/re-writing old reports.
- V30 historical report detail tools should provide report detail search, match navigation, section jumps, and same-stock timeline navigation without invoking AI or exposing raw secrets.
- User-facing text must not imply investment advice.

## tests-and-verifiers

Purpose: backend platform tests, frontend-related API contract tests, local V1 operability verifier, V2 readiness verifier, and release-candidate package verifier.

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
- `tests/test_platform_user_e2e_safety.py`
- `tests/test_platform_user_journey.py`
- `tests/test_platform_release_candidate_package.py`
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

Review focus:

- Tests cover CSRF/auth boundaries, API key custody, billing disabled behavior, quota buckets, local model capacity, and release-candidate packaging.
- Browser E2E covers ordinary user registration/login, AccountPage, masked API key custody, A-share/US/HK/crypto no-AI basic query guardrails, BYOK quick analysis, history isolation, sandbox checkout, logout, and A/B user isolation through mocked local API responses.
- E2E cleanup is dry-run by default and restricted to the `e2e+` email namespace.
- Verifiers are read-only by default and must not print secret values.
- `scripts/verify_local_v1_operability.py`, `scripts/verify_platform_v2_readiness.py`, `scripts/verify_platform_release_candidate_package.py`, and `scripts/verify_platform_user_e2e.py` must not be hidden by `.gitignore`.
- `scripts/verify_platform_billing_lifecycle.py` must also remain visible to git and print `DSA_PLATFORM_BILLING_LIFECYCLE_V1_OK` when the local billing lifecycle checks pass.
- `scripts/verify_platform_query_quality_v4.py` must remain visible to git and print `DSA_PLATFORM_QUERY_QUALITY_V4_OK` when market routing, quick-query degradation, and quota boundary checks pass.
- `scripts/verify_platform_local_functional_v5.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK` when local health, shell, platform smoke, route/quota/history/billing summary checks pass. Optional live market data may be reported as degraded; it must not be faked as successful. Sandbox billing here is not real payment.
- `scripts/verify_platform_local_usability_v6.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_USABILITY_V6_OK` only when V5 required checks are fully passed. A live 8018 account or billing route 404 after login is a hard failure in V6; the optional multi-market quick smoke checks A-share, US, HK, and crypto no-AI routes and records stale or slow market data as diagnostics instead of faking freshness.
- `scripts/verify_platform_local_query_speed_v7.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK` only when V7 diagnostics files/tests are present and required local checks pass. Optional live quick-query diagnostics may degrade when market data sources are slow, but successful snapshots must include timing/cache/source/freshness diagnostics and `ai_used=false`.
- `scripts/verify_platform_local_query_resilience_v8.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK` only when quick/no-AI timeout and fallback diagnostics pass. Optional live checks may degrade when public sources are unavailable, but successful snapshots must preserve `ai_used=false`.
- `scripts/verify_platform_local_market_source_health_v9.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_MARKET_SOURCE_HEALTH_V9_OK` only when source-health cooldown, prewarm, and diagnostics checks pass. Optional live checks may degrade when public sources are unavailable, but successful snapshots must preserve `ai_used=false`.
- `scripts/verify_platform_local_persistent_market_cache_v10.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_PERSISTENT_MARKET_CACHE_V10_OK` only when persistent-cache fallback, source-health compatibility, and diagnostics checks pass. Optional live checks may degrade when public sources are unavailable, but successful snapshots must preserve `ai_used=false`.
- `scripts/verify_platform_local_market_source_ops_v11.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK` only when local source priority/health/cache diagnostics pass. Optional live checks may degrade when the local server is unavailable, but successful source-ops payloads must preserve `ai_used=false`.
- `scripts/verify_platform_local_market_prewarm_console_v12.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK` only when the AdminPage prewarm control, V11 compatibility, and optional live no-AI prewarm checks are safe. Optional live checks may degrade when public sources are unavailable, but successful prewarm payloads must preserve `ai_used=false`.
- `scripts/verify_platform_local_market_recovery_console_v13.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK` only when the AdminPage recovery control, admin-only API boundary, V12 compatibility, reset summary, and no-AI recovery/prewarm payload checks are safe. Optional live checks may degrade when local auth or public sources are unavailable, but successful recovery payloads must preserve `ai_used=false`.
- `scripts/verify_platform_local_real_use_loop_v14.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK` only when the admin local-status API, AdminPage panel, V13 compatibility, no-AI payload boundary, and secret-redaction checks are safe. Optional live checks may create `e2e+` smoke users and must not print generated passwords.
- `scripts/verify_platform_local_user_query_loop_v15.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK` only when HomePage ordinary-user query guardrails, V14 compatibility, no-AI market-lane payload shape, and secret-redaction checks are safe. Optional live quick snapshots may degrade when public sources are unavailable, but successful snapshots must preserve `ai_used=false`.
- `scripts/verify_platform_local_browser_user_loop_v16.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK` only when the Playwright ordinary-user browser flow, V15 compatibility, and V16 live-smoke summary shape pass. Optional live multi-market smoke may degrade when public sources are unavailable, but successful snapshots must preserve `ai_used=false`.
- `scripts/verify_platform_local_watchlist_v17.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK` only when platform-user watchlist isolation, no-AI refresh summary shape, V16 compatibility, backend tests, and HomePage target tests pass.
- `scripts/verify_platform_local_watchlist_board_v18.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK` only when the watchlist board row shape, V17 compatibility, verifier tests, and HomePage board target test pass.
- `scripts/verify_platform_local_query_workspace_v19.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK` only when query workspace separation shape, V18 compatibility, verifier tests, and HomePage ordinary-user target test pass.
- `scripts/verify_platform_local_public_entry_v20.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_OK` only when ordinary platform-user entry routes remain open, admin-only routes remain protected, V19 compatibility checks pass, and App route guard tests pass.
- `scripts/verify_platform_local_public_user_flow_v21.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_PUBLIC_USER_FLOW_V21_OK` only when ordinary-user public flow, V20 compatibility, frontend target tests, and optional live 8018 smoke stay within local/no-AI/admin-boundary expectations.
- `scripts/verify_platform_local_market_refresh_v22.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_MARKET_REFRESH_V22_OK` only when force-refresh source shape, backend tests, frontend tests, and optional live refresh smoke stay no-AI and local-only.
- `scripts/verify_platform_local_history_snapshot_boundary_v23.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_HISTORY_SNAPSHOT_BOUNDARY_V23_OK` only when the historical report/current quote boundary stays no-AI and local-only.
- `scripts/verify_platform_local_history_center_v24.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V24_OK` only when the History Center filters, session-only current-quote refresh markers, no-AI refresh path, verifier tests, and focused HomePage test pass.
- `scripts/verify_platform_local_history_center_v25.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V25_OK` only when backend history filtering, persistent user-scoped refresh markers, no-AI marker guards, verifier tests, backend tests, and focused HomePage test pass.
- `scripts/verify_platform_local_history_center_v26.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V26_OK` only when validated filter persistence, backend total display, verifier tests, docs safety, and focused HomePage test pass.
- `scripts/verify_platform_local_history_export_v27.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_HISTORY_EXPORT_V27_OK` only when selected history export is owner-scoped, no-AI, secret-redacted, covered by backend/frontend tests, and documented as local-only.
- `scripts/verify_platform_local_history_detail_v30.py` must remain visible to git and print `DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK` only when report detail search, section jumps, same-stock timeline, no-AI guard, owner-scoped history reuse, docs safety, and focused HomePage test pass.
- `scripts/verify_local_v1_operability.py --auto-smoke-user` is opt-in local-only smoke support; it may create `e2e+local-smoke...` users but must not print generated passwords or delete data.

## docs-and-config

Purpose: V1 evidence, product rules, V2 launch readiness, production-evaluation env template, legal/privacy/product copy draft, handoff status, review slices, and release manifest.

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

Review focus:

- Docs must keep public-launch blockers explicit.
- `platform-production-env.example` must not contain real API keys.
- Legal/product copy is draft only and keeps "not investment advice" / "不构成投资建议".
- V2 remains a release-candidate evaluation package, not public launch approval.

## build-and-ignore-impact

Purpose: make verifier scripts visible for review while keeping generated build output and local artifacts out of commits.

Files:

- `.gitignore`

Ignored generated output to inspect but not delete:

- `static/`

Review focus:

- `.gitignore` keeps broad `verify_*.py` ignore behavior but explicitly unignores the required verifier scripts.
- `.gitignore` also unignores `scripts/verify_platform_billing_lifecycle.py`.
- `.gitignore` also unignores `scripts/verify_platform_query_quality_v4.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_functional_v5.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_usability_v6.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_query_speed_v7.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_query_resilience_v8.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_market_source_health_v9.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_persistent_market_cache_v10.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_market_source_ops_v11.py`, `scripts/verify_platform_local_market_prewarm_console_v12.py`, `scripts/verify_platform_local_market_recovery_console_v13.py`, `scripts/verify_platform_local_real_use_loop_v14.py`, `scripts/verify_platform_local_user_query_loop_v15.py`, `scripts/verify_platform_local_browser_user_loop_v16.py`, `scripts/verify_platform_local_watchlist_v17.py`, `scripts/verify_platform_local_watchlist_board_v18.py`, `scripts/verify_platform_local_query_workspace_v19.py`, `scripts/verify_platform_local_public_entry_v20.py`, `scripts/verify_platform_local_public_user_flow_v21.py`, `scripts/verify_platform_local_market_refresh_v22.py`, `scripts/verify_platform_local_history_snapshot_boundary_v23.py`, `scripts/verify_platform_local_history_center_v24.py`, `scripts/verify_platform_local_history_center_v25.py`, `scripts/verify_platform_local_history_center_v26.py`, and `scripts/verify_platform_local_history_export_v27.py`.
- `.gitignore` also unignores `scripts/verify_platform_local_history_detail_v30.py`.
- `static/` is generated by `npm run build`; do not delete it as cleanup.
- If static output must be packaged later, do that as a separate human-approved release artifact decision.

## manual-confirmation

Purpose: files that are related to the package but should receive explicit human review before being grouped with code slices.

Files:

- `requirements.txt`

Review focus:

- Confirm whether the dependency change is required for the platform API key encryption/security work.
- If unrelated, split it into a separate dependency review slice before commit.

## Suggested Review Order

1. `backend-platform-foundation`
2. `frontend-platform-experience`
3. `tests-and-verifiers`
4. `docs-and-config`
5. `build-and-ignore-impact`
6. `manual-confirmation`

This order is for human review and possible future commits only. It does not authorize commit, push, data deletion, public deployment, real payment, or production secret use.

## V28 Local History State Addendum

Purpose: add local-only owner-scoped history report management state without rewriting old AI reports.

Files:

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

Review focus:

- `analysis_history_user_states` must stay a side table and must not rewrite old AI reports.
- State updates must remain owner-scoped and no-AI.
- History Center state filtering and batch archive/restore must not delete history reports.
- `.gitignore` must keep `scripts/verify_platform_local_history_state_v28.py` visible.
- V28 remains local-only, not real payment, not public launch approval, and not investment advice.

## V29 Local History Operations Addendum

Purpose: improve local History Center operations without invoking AI or rewriting old reports.

Files:

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

Review focus:

- `note_search` must remain owner-scoped and must search local notes only.
- Default active history view must not delete archived reports.
- Batch important/read must stay no-AI and must not consume quota.
- Date group headers are presentation only and must not rewrite report timestamps.
- `.gitignore` must keep `scripts/verify_platform_local_history_ops_v29.py` visible.
- `scripts/verify_platform_local_history_ops_v29.py` must print `DSA_PLATFORM_LOCAL_HISTORY_OPS_V29_OK` only when note search, active default, date groups, batch important/read, and docs safety checks pass.
- V29 remains local-only, not real payment, not public launch approval, and not investment advice.

## V30 Local History Detail Addendum

Purpose: improve local historical report detail reading without invoking AI or adding a new timeline endpoint.

Files:

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

Review focus:

- Report detail search must search visible safe report fields and must not expose raw secrets.
- Same-stock timeline must reuse existing owner-scoped history list records and must not add a separate timeline endpoint.
- Section jumps use `sectionIdPrefix` anchors in `ReportSummary` and should remain display-only.
- Detail search, section jumps, and timeline navigation must stay no-AI and must not consume quota.
- `.gitignore` must keep `scripts/verify_platform_local_history_detail_v30.py` visible.
- `scripts/verify_platform_local_history_detail_v30.py` must print `DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK` only when report detail search, search navigation, section jumps, same-stock timeline, no-AI guard, docs safety, and focused HomePage test pass.
- V30 remains local-only, not real payment, not public launch approval, and not investment advice.

## V48 Production Readiness Addendum

Purpose: add a local-only, machine-checkable production readiness preflight that makes public-launch blockers visible to admins without connecting real payment, real secrets, public infrastructure, or AI.

Files:

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

Review focus:

- `GET /api/v1/platform/admin/production-readiness` must remain admin-only and must not call AI or live market data sources.
- The readiness payload must keep `launch_decision=blocked` until real payment, domain, HTTPS/WAF, data-source commercial license, legal terms, privacy policy, monitoring, and backup/restore approvals are present.
- Secret-like environment values must be redacted from payloads, tests, docs, and frontend rendering.
- AdminPage should show the blocked production preflight clearly without implying the platform is publicly ready.
- `.gitignore` must keep `scripts/verify_platform_production_readiness_v48.py` visible.
- `scripts/verify_platform_production_readiness_v48.py` must print `DSA_PLATFORM_PRODUCTION_READINESS_V48_OK` only when service, endpoint, frontend API/UI, docs, secret redaction, and V48 backend tests pass.
- V48 remains local-only, not real payment, not production deployment, not legal approval, not data-source license approval, and not investment advice.

## V49 Billing Provider Boundary Addendum

Purpose: recognize real payment provider configuration requirements while failing closed locally until a live adapter, merchant approval, webhook reconciliation, refunds, invoices, and rollback are implemented.

Files:

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

Review focus:

- `get_payment_provider_status()` must expose only config-key names and readiness booleans, never secret values.
- Stripe-like real provider configuration must fail closed as `billing_provider_not_ready` when required config is missing.
- Even with all local placeholder config present, checkout must return `billing_provider_adapter_not_implemented` and must not perform a real payment or network call.
- `/api/v1/billing/account` may show sanitized provider readiness, but must not show real secret values.
- Production readiness must keep real payment blocked until configuration, adapter, merchant, webhook, reconciliation, refund, invoice, and rollback approval exist.
- `.gitignore` must keep `scripts/verify_platform_billing_provider_boundary_v49.py` visible.
- `scripts/verify_platform_billing_provider_boundary_v49.py` must print `DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK` only when provider status, endpoint failures, production readiness linkage, secret redaction, and V49 tests pass.
- V49 remains local-only, not real payment, not public launch approval, and not investment advice.

## V50 Production Env Gates Addendum

Purpose: make launch-blocking production approvals explicit in the env template and verifier stack.

Files:

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

Review focus:

- `platform-production-env.example` must keep auth/CSRF enabled and debug/CORS/public search/expensive enrichment disabled by default.
- Real payment, payment webhook, domain, HTTPS, WAF, market-data license, legal terms, privacy policy, monitoring, and backup/restore gates must be explicit `false`.
- `DSA_ANALYSIS_NOT_INVESTMENT_ADVICE` must remain explicit `true`.
- Stripe-like provider placeholders must be present but blank, so template placeholders cannot be mistaken for working credentials.
- V2 readiness and release package verifiers must reject missing or unsafe production gate defaults.
- `.gitignore` must keep `scripts/verify_platform_production_env_gates_v50.py` visible.
- V50 remains local-only, not production deployment, not real payment, and not investment advice.

## V51 Backup Restore Drill Addendum

Purpose: add a repeatable local SQLite backup/restore dry-run tool with machine-readable evidence.

Files:

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

Review focus:

- The backup service must use separate backup/restored files and must not mutate the source database.
- The runner must default to a timestamped `local/backups/dry-runs` output path and must fail if no database is supplied.
- Verification must run on temporary databases by default, not the user's live database.
- The payload must report `destructive=false`, `ai_used=false`, integrity checks, source unchanged, and row-count match.
- `.gitignore` must keep `scripts/verify_platform_backup_restore_drill_v51.py` visible.
- V51 remains local-only, not production backup approval, not public launch approval, not real payment, and not investment advice.

## V52 Ops Health Addendum

Purpose: add an admin-only, read-only local operations health status for database, safety config, billing readiness, backup tooling, and verifier availability.

Files:

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

Review focus:

- `GET /api/v1/platform/admin/ops-health` must remain admin-only.
- Ops health must be read-only, no-AI, no live market-data, and no payment processing.
- Payloads must not expose database absolute paths, API keys, webhook secrets, or tokens.
- Checks should cover database reachability, safe config flags, billing provider readiness, backup runner/verifier availability, and production readiness verifier availability.
- `.gitignore` must keep `scripts/verify_platform_ops_health_v52.py` visible.
- V52 remains local-only, not production monitoring approval, not public launch approval, not real payment, and not investment advice.

## V53 Ops Health Panel Addendum

Purpose: show V52 ops health in AdminPage so local operators can review health status from the UI.

Files:

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

Review focus:

- AdminPage must call `adminOpsHealth()` with the other admin snapshots and refresh it on manual refresh.
- The panel must show overall status, summary counts, category chips, and degraded check details without exposing secrets.
- It must remain read-only and not trigger AI, payment processing, or market-data fetches.
- `.gitignore` must keep `scripts/verify_platform_ops_health_panel_v53.py` visible.
- V53 remains local-only, not production monitoring approval, not public launch approval, and not investment advice.

## V54 Local User Acceptance Addendum

Purpose: verify the local anonymous/free query journey before handing the browser back to the user.

Files:

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

Review focus:

- Anonymous snapshot queries must remain no-AI and must not require platform login.
- The free report UI must keep the rich no-AI sections visible for user retention.
- `00700.HK` must get a clearly marked latest-historical-close fallback when realtime HK quote is unavailable.
- `scripts/verify_platform_local_user_acceptance_v54.py` must stay visible despite the broad `verify_*.py` ignore rule.
- V54 remains local-only, not public launch approval, not real payment, and not investment advice.

## V55 Local Product Experience Addendum

Purpose: improve the local first-visit product experience so ordinary users can query before login, receive a richer free no-AI report, and see non-blocking registration guidance.

Files:

- `src/services/basic_query_service.py`
- `api/v1/schemas/basic_query.py`
- `tests/test_basic_query_no_ai.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `tests/test_platform_local_product_experience_v55.py`
- `scripts/verify_platform_local_product_experience_v55.py`
- `docs/superpowers/plans/2026-07-06-dsa-v55-local-product-experience.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Review focus:

- Anonymous users must still be able to run quick no-AI queries without platform login.
- `retention_brief` must be deterministic and must not call `AnalysisService`, public search, or paid AI.
- The guest conversion guide must not clear the current snapshot or force registration before query.
- `scripts/verify_platform_local_product_experience_v55.py` must stay visible despite the broad `verify_*.py` ignore rule.
- V55 remains local-only, not public launch approval, not real payment, and not investment advice.

## V56 Local User Retention Addendum

Purpose: close the local ordinary-user retention loop after the V55 guest-first query: a guest can query AAPL, register/login, save the current no-AI result, add it to watchlist, logout/login, and still see private history/watchlist state.

Files:

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

Review focus:

- `/api/v1/platform/history/snapshot` must require a platform session, reject AI-used snapshots, write `platform_user_id`, and avoid secret leakage in audit/context data.
- HomePage must preserve the current guest snapshot through register/login and use the snapshot symbol for save/watchlist actions even when the search input is reset.
- The snapshot retention panel must expose free no-AI, platform API, BYOK, and local-model quota/mode boundaries without plaintext keys.
- Playwright E2E must remain mock-backed and must not use real API keys or real payment.
- `scripts/verify_platform_local_user_retention_v56.py` must stay visible despite the broad `verify_*.py` ignore rule.
- V56 remains local-only, not public launch approval, not real payment, and not investment advice.

## V57 Local News And K-Line Forecast Lab Addendum

Purpose: make the free query experience richer without increasing platform cost: no-AI snapshots show local information lanes, a Kronos-ready K-line forecast lab preview, and a premium feature ladder.

Files:

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

Review focus:

- `news_center` and `kline_forecast` must remain no-AI and must not call public search or paid APIs.
- `kline_forecast.kronos_model_used` must stay `false` until a real Kronos adapter and model/data approval gate exist.
- HomePage must show `basic-query-news-center`, `basic-query-kline-forecast-lab`, and `basic-query-premium-feature-ladder` without blocking anonymous query.
- `scripts/verify_platform_local_news_kline_v57.py` must stay visible despite the broad `verify_*.py` ignore rule.
- V57 remains local-only, not public launch approval, not real payment, and not investment advice.

## V58 Kronos Sandbox Addendum

Purpose: add a real Kronos model adapter lane with an honest local-runtime boundary. The UI can run a local sandbox check, show dependency/model readiness, fall back to deterministic rules when disabled or unavailable, and preserve a local record/backtest trail.

Files:

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
- `.gitignore`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Review focus:

- Public `kronos-forecast` readiness/fallback must remain no-AI and no-public-search.
- `require_model=true` must require a signed-in pro/premium/enterprise/admin user and must not silently return fallback as a real model result.
- `kronos_model_used` must only be true after the configured local Kronos predictor actually runs.
- JSONL forecast records must remain local metadata and must not contain API keys or secrets.
- `scripts/verify_platform_kronos_sandbox_v58.py` must stay visible despite the broad `verify_*.py` ignore rule.
- V58 remains local-only, not public launch approval, not real payment, not hosted model SLA, and not investment advice.

## V59 A-Stock-Data POC Addendum

Purpose: enrich A-share free quick snapshots with local, no-AI data lanes inspired by `a-stock-data`: announcements, fund flow, sector/concept context, research, and dragon-tiger list. This is a local adapter POC, not a public data-source license approval.

Files:

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

Review focus:

- `a_share_enrichment` must only run for `route.market == "cn"` and must never block US, HK, or crypto quick snapshots.
- Quick mode must keep `ai_used=false` and `public_search_used=false`; public search, long AI summaries, and real-time source links stay deep/premium/configured-source work.
- Adapter failures must degrade into visible channel statuses instead of failing the whole snapshot.
- HomePage must render `basic-query-a-share-enrichment` with Chinese/English language consistency and without exposing secrets.
- `scripts/verify_platform_a_stock_data_poc_v59.py` must stay visible despite the broad `verify_*.py` ignore rule and print `DSA_PLATFORM_A_STOCK_DATA_POC_V59_OK` only when V59 markers are present.
- V59 remains local-only, not public launch approval, not real payment, not market-data licensing approval, and not investment advice.

## V60 A-Stock-Data Source Addendum

Purpose: connect the local `simonlin1212/a-stock-data` checkout as a configurable A-share source adapter with cache, rate limit, source-mode diagnostics, and degraded fallback. This remains local-only and does not approve public data-source redistribution.

Files:

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

Review focus:

- `A_STOCK_DATA_SOURCE_MODE` must default safely and external calls disabled by default unless explicitly enabled or injected in tests.
- Cache and rate limit must prevent repeated source calls from slowing or blocking free quick queries.
- A single failed channel must mark degradation without hiding successful channels.
- Schema and TypeScript can expose non-secret diagnostics, but must not expose API keys or production secrets.
- `scripts/verify_platform_a_stock_data_v60.py` must stay visible and print `DSA_PLATFORM_A_STOCK_DATA_V60_OK` only when the V60 markers are present.
- V60 remains local-only, not real payment, not production deployment, not market-data licensing approval, and not investment advice.

## V61 A-Stock-Data UI Addendum

Purpose: expose the configurable A-share source adapter in HomePage so local users can switch local rules, `a-stock-data`, or off mode and run 600519/000001 sample probes without AI or public search.

Files:

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

Review focus:

- `a_share_source_mode` must remain limited to `poc|a_stock_data|off`.
- UI diagnostics may show cache counts and local repository revision, but must not expose API keys or source credentials.
- Probe buttons for `600519` and `000001` must use refreshed no-AI snapshots and the selected source mode.
- `scripts/verify_platform_a_stock_data_ui_v61.py` must stay visible and print `DSA_PLATFORM_A_STOCK_DATA_UI_V61_OK` only when the V61 markers are present.
- V61 remains local-only, not real payment, not production deployment, not market-data licensing approval, and not investment advice.

## V62 A-Stock-Data Useful Data Addendum

Purpose: make the A-share free snapshot visibly useful by mapping the local `a-stock-data` adapter to public-source parsers for CNINFO announcements and Eastmoney fund-flow, sector, research, and dragon-tiger checks. The HomePage default applies this source mode only for A-share inputs.

Files:

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

Review focus:

- V62 remains local-only and does not approve production deployment, real payment, market-data redistribution, or investment advice.
- Quick mode must remain `ai_used=false` and `public_search_used=false`.
- A failed or empty upstream channel must remain visible as a checked degraded card, not a vague reserved-lane placeholder.
- Shanghai CNINFO fallback must use `gssh0{code}`, and 600519 / 贵州茅台 keeps useful local sector fallback tags if the public sector endpoint is empty or slow.
- `a_stock_data` mode may use a 2.5s default timeout for real public endpoints; local POC mode keeps the 1.2s fast fallback.
- HomePage should default A-share inputs to `a_stock_data` but must not route AAPL/BTC/HK symbols through the A-share source mode.
- `scripts/verify_platform_a_stock_data_useful_v62.py` must stay visible and print `DSA_PLATFORM_A_STOCK_DATA_USEFUL_V62_OK` only when the V62 markers are present.

## V63 A-Stock-Data Experience Addendum

Purpose: make the A-share enrichment block easier for ordinary users to understand by adding a first-read `reader_summary` above the raw channel cards. The summary explains why the result is worth reading, what channels were checked, which lanes are missing/degraded, and what premium can unlock.

Files:

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

Review focus:

- V63 remains local-only and does not approve production deployment, real payment, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and `public_search_used=false`.
- The `reader_summary` must not hide channel cards; it is a first-read layer only.
- Missing or degraded lanes must be explained as checked-but-empty/degraded, not as silent blanks.
- Premium copy should describe a data-channel upgrade, not separate visible features: free and premium show the same modules, while premium/API modes use platform API, user API, approved feeds, or local models for fresher and deeper output.
- `scripts/verify_platform_a_stock_data_experience_v63.py` must stay visible and print `DSA_PLATFORM_A_STOCK_DATA_EXPERIENCE_V63_OK` only when the V63 markers are present.

## V64 A-Stock-Data Details Addendum

Purpose: make A-share enrichment cards more useful by adding structured `details` rows to each channel. The raw cards still show summary/action/source, but users can now scan key fields such as announcement date, fund-flow net amount, industry, research rating, and dragon-tiger net buy.

Files:

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

Review focus:

- V64 remains local-only and does not approve production deployment, real payment, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and `public_search_used=false`.
- `details` must be compact scan aids; they do not replace the channel summary/action text.
- Missing or degraded lanes must remain explicit instead of silently disappearing.
- `scripts/verify_platform_a_stock_data_details_v64.py` must stay visible and print `DSA_PLATFORM_A_STOCK_DATA_DETAILS_V64_OK` only when the V64 markers are present.

## V65 Free-Value Experience Addendum

Purpose: make the free no-AI stock result feel useful in the first screen by showing a clear value summary before deeper details. The summary highlights the conclusion, current watch points, risk boundary, and what deep/premium analysis can unlock, while diagnostic internals are collapsed by default.

Files:

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

Review focus:

- V65 remains local-only and does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and `public_search_used=false`.
- The first-screen summary must not replace the detailed no-AI report; it is a user-facing entry layer only.
- The free summary must keep visible entries for News Center and K-line forecast so those features remain discoverable after query.
- Data diagnostics should remain available but collapsed by default so free users see product value before technical internals.
- `scripts/verify_platform_free_value_v65.py` must stay visible and print `DSA_PLATFORM_FREE_VALUE_V65_OK` only when the V65 markers are present.

## V66 Productized Snapshot Addendum

Purpose: make the free quick-query result read like a professional dashboard instead of a thin quote response. Free and premium now keep the same visible modules; the difference is the data channel, where free uses a free web source/local public data and premium uses an API-backed source, BYOK, platform API, or local model for fresher and deeper output.

Files:

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

Review focus:

- V66 remains local-only and does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and avoid public search by default.
- `basic-query-professional-overview` must appear before the free value summary and show trend score, risk level, data channel, support/resistance, and module navigation.
- Chinese mode must keep the new user-facing labels in Chinese: `专业速览`, `趋势评分`, `风险等级`, `数据通道`, `模块导航`, `行情概览`, `技术面`, `资讯中心`, and `K线预测`.
- The copy must describe `免费网络源` and `高级 API 源` as channel differences, not locked features.
- `scripts/verify_platform_productized_snapshot_v66.py` must stay visible and print `DSA_PLATFORM_PRODUCTIZED_SNAPSHOT_V66_OK` only when the V66 markers are present.

## V67 Free Research Board Addendum

Purpose: turn the free query result from a module list into a readable research board. The board summarizes news radar, K-line read, peer/sector context, and risk explanation directly after the professional overview, so free users see useful scan value before deeper details.

Files:

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

Review focus:

- V67 remains local-only and does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and avoid public search by default.
- `basic-query-free-research-board` must show `资讯雷达`, `K线推演`, `同业/板块`, and `风险解释` with concrete content, not placeholder-only copy.
- Free and premium keep the same visible research modules; premium/API modes only improve freshness, source links, configured feeds, and model depth.
- `scripts/verify_platform_free_research_board_v67.py` must stay visible and print `DSA_PLATFORM_FREE_RESEARCH_BOARD_V67_OK` only when V67 markers are present.

## V68 Free Commercial Journey Addendum

Purpose: make the top of the free query result feel like a complete guided report. The new journey block appears after the primary summary and before deeper modules, telling visitors what to read first, what research modules are already open, and why premium/API mode improves source quality rather than hiding the core page.

Files:

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

Review focus:

- V68 remains local-only and does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and avoid public search by default.
- `basic-query-commercial-journey` must show `免费查询完整路径`, `免费版已开放`, `不登录也能查`, and `高级版只换数据源`.
- The block must explain same visible modules: quote, technicals, news, K-line, peers, and risk.
- Premium/API copy must describe realtime news, filings/SEC, Kronos/API model, and BYOK as data-source/model-depth upgrades, not hard locks on the visible report.
- `scripts/verify_platform_free_commercial_journey_v68.py` must stay visible and print `DSA_PLATFORM_FREE_COMMERCIAL_JOURNEY_V68_OK` only when V68 markers are present.

## V69 Free Data Depth Addendum

Purpose: make the free query result contain concrete useful data, not only retention copy. The new board appears after the commercial journey and summarizes quote, volume, valuation, technical structure, event lanes, peers, and risk boundaries with the same visible module structure that premium will later enrich through API-backed sources.

Files:

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

Review focus:

- V69 remains local-only and does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and avoid public search by default.
- `basic-query-data-depth-board` must show `免费版真实数据面板`, `美股重点数据`, `A股重点数据`, `核心数据`, `技术结构`, `资讯与事件`, and `同业与风险`.
- The board should use existing snapshot fields and must not trigger extra AI/model/API/public-search cost.
- `scripts/verify_platform_free_data_depth_v69.py` must stay visible and print `DSA_PLATFORM_FREE_DATA_DEPTH_V69_OK` only when V69 markers are present.

## V70 Free Detail Readability Addendum

Purpose: make the free data-depth board easier to read and inspect. The new detail layer adds expandable quote fields, event checklist wording, peer comparison rows, and K-line trigger cards without changing the free quick path into an AI/API/search workflow.

Files:

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

Review focus:

- V70 remains local-only and does not approve production deployment, real payment, production secrets, market-data redistribution, or investment advice.
- Free quick mode must remain `ai_used=false` and avoid public search by default.
- `basic-query-data-detail-core`, `basic-query-data-detail-events`, `basic-query-peer-table`, and `basic-query-kline-triggers` must stay visible in the free result path.
- The free and premium versions keep the same visible modules; premium/API mode only improves freshness, source links, configured feeds, and model depth.
- `src/notification_sender/feishu_sender.py` must degrade when `lark_oapi` import raises `OSError`, so Windows local socket pressure does not prevent the API app from starting.
- `scripts/verify_platform_free_detail_readability_v70.py` must stay visible and print `DSA_PLATFORM_FREE_DETAIL_READABILITY_V70_OK` only when V70 markers are present.

## V71 Free Multimarket Modules Addendum

Scope: local-only free query value upgrade. This slice keeps A-share, US equity, HK equity, and crypto free/no-AI results on the same visible module structure when the backend returns only a basic snapshot.

Changed files:

- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_multimarket_v71.py`
- `tests/test_platform_free_multimarket_v71.py`
- `docs/superpowers/plans/2026-07-08-dsa-v71-free-multimarket-modules.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Review notes:

- Free and premium users should see the same visible cards first; premium/API only changes source quality, freshness, model depth, and persistence.
- Backend-provided English `comparisonTargets` must still be localized in Chinese mode; this covers Hong Kong and crypto live-result paths where fallback peers are not used.
- No AI calls, no public search, no real payment, no production deployment, and no real API Key are part of this local boundary.
- The fallback peer table and K-line triggers are local rules and source checklists only; they are not investment advice.

Acceptance:

- `scripts/verify_platform_free_multimarket_v71.py` must stay visible and print `DSA_PLATFORM_FREE_MULTIMARKET_V71_OK` only when V71 implementation, tests, docs, release package coverage, and git visibility markers are present.

## V72 Free Peer Quotes Addendum

Scope: local-only free query value upgrade. This slice makes the free no-AI peer/market comparison modules show available reference quote values instead of only names and explanations.

Changed files:

- `src/services/basic_query_service.py`
- `api/v1/schemas/basic_query.py`
- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `tests/test_basic_query_no_ai.py`
- `tests/test_market_data_cache.py`
- `scripts/verify_platform_free_peer_quotes_v72.py`
- `tests/test_platform_free_peer_quotes_v72.py`
- `docs/superpowers/plans/2026-07-08-dsa-v72-free-peer-quotes.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`

Review notes:

- Free and premium users should see the same comparison modules; premium/API only improves source quality, freshness, source links, configured feeds, and model depth.
- Reference quote fetches use a short timeout and existing cache. Missing reference quotes must degrade to unavailable and must not block the main snapshot.
- If the primary platform reference quote source returns empty, the free lane may use the no-key Yahoo chart fallback for public benchmark symbols.
- Cache coverage confirms the main quote and reference quotes are not fetched again on the second snapshot.
- No AI calls, no public search, no real payment, no production deployment, and no real API Key are part of this local boundary.
- All copy remains information analysis only and not investment advice.

Acceptance:

- `scripts/verify_platform_free_peer_quotes_v72.py` must stay visible and print `DSA_PLATFORM_FREE_PEER_QUOTES_V72_OK` only when V72 implementation, tests, docs, release package coverage, and git visibility markers are present.

## V73 Free Broker Conversion Addendum

Scope: local-only free query conversion upgrade. This slice reshapes the first result screen into a broker-style decision cockpit so visitors see a useful conclusion, evidence chain, risk boundary, and upgrade rationale before scrolling.

Changed files:

- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_broker_conversion_v73.py`
- `tests/test_platform_free_broker_conversion_v73.py`
- `docs/superpowers/plans/2026-07-08-dsa-v73-free-broker-conversion.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `.gitignore`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`

Review notes:

- The free first screen now answers `现在值不值得继续看` before presenting the deeper module ladder.
- Free and premium users still see the same visible research structure; premium/API only improves real-time source links, configured feeds, and model depth.
- The cockpit uses existing no-AI snapshot data and does not introduce AI calls, public search, real payment, production deployment, or real API Key handling.
- Copy keeps the `不构成投资建议` boundary visible.

Acceptance:

- `scripts/verify_platform_free_broker_conversion_v73.py` must stay visible and print `DSA_PLATFORM_FREE_BROKER_CONVERSION_V73_OK` only when V73 implementation, tests, docs, release package coverage, and git visibility markers are present.

## V93 Free Retention And API Trial Addendum

Scope: local-only free retention upgrade. Guests keep the no-AI research entry; signed-in free users receive a bounded weekly platform-API trial. Premium users may continue to use the platform API, their own API key, or a configured local model according to quota policy.

Changed files:

- `api/v1/endpoints/analysis.py`
- `api/middlewares/auth.py`
- `api/v1/endpoints/stocks.py`
- `api/v1/schemas/stocks.py`
- `src/platform_accounts.py`
- `src/services/stock_service.py`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/components/retention/FreeApiTrialPanelV93.tsx`
- `apps/dsa-web/src/components/retention/QueryChangeSummaryV93.tsx`
- `apps/dsa-web/src/components/retention/queryChangeTracker.ts`
- `apps/dsa-web/src/components/retention/__tests__/FreeApiTrialPanelV93.test.tsx`
- `apps/dsa-web/src/components/retention/__tests__/queryChangeTracker.test.ts`
- `tests/test_platform_free_retention_v93.py`
- `tests/test_auth_api.py`
- `docs/CHANGELOG.md`
- `docs/superpowers/plans/2026-07-10-dsa-v93-free-retention-and-api-trial.md`
- `scripts/verify_platform_release_candidate_package.py`

Review focus:

- Free API trial quota is reserved before asynchronous queue admission and released when duplicate or failed submissions are rejected; it must not create hidden platform-model cost.
- Guest no-AI lookup remains available without login. Login is required only for saved history, watchlist, account state, and the bounded platform-API trial.
- API trial feedback must show success, rejection, or failure in the active UI language; browser storage failure must not be presented as a valid historical comparison.
- Public Yahoo history fallback accepts supported US/HK-style symbols only and must not be used for A-share, Japan, Korea, Taiwan, Canada, or Australia exchange symbols.
- Same visible research modules remain available in free mode; premium/API improves freshness, source links, configured feeds, and model depth.
- No real payment, production deployment, production secrets, or investment advice is part of this local slice.

## V95 Free API Trial Result Loop Addendum

Scope: local-only retention UX for the bounded free platform-API trial.

Changed files:

- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`
- `apps/dsa-web/e2e/platform-user-e2e.spec.ts`
- `apps/dsa-web/src/components/retention/FreeApiTrialTaskStatusV95.tsx`
- `apps/dsa-web/src/components/retention/__tests__/FreeApiTrialTaskStatusV95.test.tsx`
- `tests/test_platform_free_retention_v93.py`
- `tests/test_auth_api.py`
- `docs/superpowers/plans/2026-07-10-dsa-v95-free-api-trial-result-loop.md`

Review focus:

- The accepted task id is carried from async submission into the HomePage result card.
- Accepted tasks are registered locally before SSE terminal events are merged.
- Pending, processing, completed, failed, and cancelled states are mapped honestly and localized.
- Completion reports history refresh; failure does not masquerade as a usable report.
- The weekly quota boundary and no-AI guest path remain unchanged.
- No payment, production key, public search, or unbounded platform API spend is introduced.

Acceptance:

- Targeted frontend tests and HomePage regression tests pass.
- The production frontend build passes.
- The three platform browser E2E paths pass, including the completed free-trial result loop.
- The combined 128-test backend command passes without platform-auth environment leakage.
- Release package coverage includes every V95 file.

## V96 Free Trial Report Conversion Addendum

Scope: local-only conversion UX after a bounded free platform-API trial completes.

Changed files:

- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/e2e/platform-user-e2e.spec.ts`
- `apps/dsa-web/src/components/retention/FreeApiTrialConversionV96.tsx`
- `apps/dsa-web/src/components/retention/freeApiTrialReport.ts`
- `apps/dsa-web/src/components/retention/__tests__/FreeApiTrialConversionV96.test.tsx`
- `apps/dsa-web/src/components/retention/__tests__/freeApiTrialReport.test.ts`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-10-dsa-v96-free-trial-report-conversion.md`

Review focus:

- Only a same-symbol report created after the trial began and outside the history baseline may be auto-opened.
- History refresh races must not leave the report hidden or open an older record.
- The conversion band is localized, leaves the complete report visible, and routes only to the existing account page.
- Free weekly quota, no-AI lookup, platform/BYOK/local separation, and local-only payment boundaries remain unchanged.

Acceptance:

- Helper and conversion-component tests pass.
- HomePage and stock-pool regression tests pass.
- The browser E2E proves registration, free lookup, one platform-API trial, automatic report opening, report content, and account navigation.
- Production frontend build and existing backend/release/local-operability gates pass.

## V97 Free Retention Funnel Addendum

Scope: local-only, privacy-bounded measurement of the free-user conversion path.

Changed files:

- `api/middlewares/auth.py`
- `api/v1/endpoints/platform.py`
- `api/v1/schemas/platform.py`
- `src/platform_retention_funnel.py`
- `tests/test_platform_retention_funnel_v97.py`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/utils/retentionFunnel.ts`
- `apps/dsa-web/src/utils/__tests__/retentionFunnel.test.ts`
- `apps/dsa-web/src/components/admin/RetentionFunnelPanelV97.tsx`
- `apps/dsa-web/src/components/admin/__tests__/RetentionFunnelPanelV97.test.tsx`
- `apps/dsa-web/src/components/history/StockBarItem.tsx`
- `apps/dsa-web/src/components/i18n/UiLanguageToggle.tsx`
- `apps/dsa-web/src/components/layout/__tests__/Shell.test.tsx`
- `apps/dsa-web/src/components/report/__tests__/ReportMarkdownDrawer.test.tsx`
- `apps/dsa-web/src/pages/AdminPage.tsx`
- `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/e2e/platform-user-e2e.spec.ts`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-10-dsa-v97-free-retention-funnel.md`

Review focus:

- The event endpoint is the only new anonymous write boundary and must remain exact-path exempt, rate-limitable, schema-forbidden for extra fields, and fixed to five events/five sources.
- The raw browser session id never leaves the request-processing boundary; only a 24-character SHA-256 prefix is stored for local aggregation.
- The admin summary is monotonic from the free-query cohort and never returns internal hashes or user identifiers.
- The general admin audit response removes retention hashes even though the internal service still needs them for aggregation.
- Telemetry calls are best-effort and cannot change quota, analysis, report, registration, or navigation outcomes.
- No real payment, production tracking provider, cookies beyond existing local session behavior, real API Key, or investment advice is introduced.

Acceptance:

- Backend V97 tests prove whitelist validation, hashing, deduplication, ownership, admin authorization, aggregate math, and audit-response redaction.
- Frontend tests prove stable local session behavior and complete Chinese/English funnel labels.
- Browser E2E proves the five events follow the actual guest-to-account flow in order.
- Build, platform regressions, release package, V1 operability, V2 readiness, live 8018, and dirty-tree gates pass.

## V99 Watchlist Event Radar Addendum

Scope: local-only, user-owned daily watchlist review and event prioritization.

Backend platform foundation:

- `src/platform_watchlist.py`
- `src/platform_watchlist_radar.py`
- `api/v1/endpoints/platform.py`
- `api/v1/schemas/platform.py`

Frontend platform experience:

- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/components/radar/WatchlistEventRadarV99.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`

Tests and verifiers:

- `tests/test_platform_watchlist_event_radar_v99.py`
- `tests/test_platform_watchlist_event_radar_v99_verifier.py`
- `scripts/verify_platform_watchlist_event_radar_v99.py`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/components/radar/__tests__/WatchlistEventRadarV99.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

Docs and config:

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v99-watchlist-event-radar.md`

Review focus:

- User identity owns the complete request path; no global alert or cross-user watchlist state is reused.
- Source events require a traceable persisted URL and do not promote placeholder text into news.
- Free/paid differences affect processing capacity only; both plans retain the same information architecture.
- No AI quota, public search, live feed ingestion, real payment, production key, or user-data deletion is introduced.

## V100 Private Watchlist Alert Loop Addendum

Scope: local-only, user-owned private alerts and persisted daily review history.

Backend platform foundation:

- `src/platform_watchlist_automation.py`
- `src/platform_watchlist_radar.py`
- `src/storage.py`
- `api/v1/endpoints/platform.py`
- `api/v1/schemas/platform.py`

Frontend platform experience:

- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/components/radar/WatchlistAlertLoopV100.tsx`
- `apps/dsa-web/src/components/radar/WatchlistEventRadarV99.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`

Tests and verifiers:

- `tests/test_platform_watchlist_alert_loop_v100.py`
- `tests/test_platform_watchlist_alert_loop_v100_verifier.py`
- `tests/test_platform_security_boundaries.py`
- `tests/test_platform_watchlist_event_radar_v99.py`
- `scripts/verify_platform_watchlist_alert_loop_v100.py`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/components/radar/__tests__/WatchlistAlertLoopV100.test.tsx`
- `apps/dsa-web/src/components/radar/__tests__/WatchlistEventRadarV99.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

Docs and config:

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v100-watchlist-alert-loop.md`

Review focus:

- Every stored rule, alert event, and radar run is owned by the current platform user.
- First-run MA20 state is a baseline only; crossing requires a previous saved run and a real side change.
- Same-user run/save/disable writes are serialized locally, and A-share/HK persisted source-code variants are matched deterministically.
- HomePage rejects stale-generation private writes and cross-user responses, including watchlist and API-key completion paths.
- Free and paid users share the visible loop; only rule and processing capacity differ.
- No AI quota, public search, real payment, production key, deployment, or user-data deletion is introduced.

## V101 Free Historical Trend Research Addendum

Scope: guest-visible, no-AI historical price evidence for free quick analysis.

Frontend and API client:

- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/components/research/FreeKlineResearchV101.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`

Tests and verifier:

- `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- `apps/dsa-web/src/components/research/__tests__/FreeKlineResearchV101.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `tests/test_platform_free_kline_research_v101_verifier.py`
- `scripts/verify_platform_free_kline_research_v101.py`

Docs and config:

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v101-free-kline-research.md`

Review focus:

- Guest quick analysis gets evidence depth without login or AI quota.
- Actual history and deterministic moving averages remain visibly separate from forecast/model copy.
- Public source failures degrade without raw errors or secret disclosure.
- Mobile layout and range controls remain stable and do not widen the page.

## V102 A-share Free Query Speed Addendum

Scope: local-only A-share free-query latency and source-resilience hardening.

Backend platform foundation:

- `src/services/a_share_enrichment_service.py`
- `src/services/basic_query_service.py`

Tests and verifiers:

- `tests/test_a_share_enrichment_service.py`
- `tests/test_platform_market_data_freshness_v92.py`
- `tests/test_platform_a_share_free_query_speed_v102_verifier.py`
- `tests/test_platform_release_candidate_package.py`
- `scripts/verify_platform_a_share_free_query_speed_v102.py`
- `scripts/verify_platform_release_candidate_package.py`

Docs and config:

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v102-a-share-free-query-speed.md`

Review focus:

- Five independent public-data channels execute in stable output order under one bounded parallel budget.
- Budget expiration returns promptly and remains explicitly degraded, including on a cached repeat response.
- A cooling reference-quote source is skipped without removing the visible comparison row.
- Only the built-in adapter shares cache across request-scoped instances; injected/custom adapters retain isolated state.
- No AI quota, public search, real payment, production key, deployment, user-data deletion, or fabricated freshness is introduced.

## V103 Free Daily Research Cockpit Addendum

Scope: local-only free-user daily retention and watchlist research prioritization.

Backend platform foundation:

- `src/platform_watchlist_radar.py`
- `api/v1/schemas/platform.py`

Frontend platform experience:

- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/components/radar/DailyResearchCockpitV103.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`

Tests and verifiers:

- `tests/test_platform_daily_research_cockpit_v103.py`
- `tests/test_platform_watchlist_alert_loop_v100.py`
- `tests/test_platform_free_daily_research_cockpit_v103_verifier.py`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/components/radar/__tests__/DailyResearchCockpitV103.test.tsx`
- `apps/dsa-web/src/components/radar/__tests__/WatchlistEventRadarV99.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_free_daily_research_cockpit_v103.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Docs and config:

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v103-free-daily-research-cockpit.md`

Review focus:

- Stale or degraded rows cannot enter the strong-confirmation group.
- Daily groups remain deterministic, top-three bounded, no-AI, and user-scoped.
- Symbol drill-down does not consume quota; only the existing explicit platform API trial action can do so.
- Chinese and English copy expose the same research, confidence, quota, and safety boundaries.
- No public search, real payment, production key, deployment, user-data deletion, fabricated freshness, or investment advice is introduced.
- Review private-response generation and `userId` checks together; either check alone is insufficient during logout or account switching.
- Review current-plan limits at both listing and execution, same-user local write serialization, source URL deduplication, finite numeric validation, CSRF, and delete-rate limiting.
## V104 Market Data Screening And Condition Alerts Addendum

### backend-platform-foundation

- `api/v1/endpoints/alphasift.py`
- `api/middlewares/auth.py`
- `src/services/market_screening_brief.py`
- `src/services/alphasift_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/alphasift.ts`
- `apps/dsa-web/src/api/error.ts`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/i18n/uiText.ts`
- `apps/dsa-web/src/pages/StockScreeningPage.tsx`
- `apps/dsa-web/src/components/screening/screeningModelV104.ts`
- `apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx`
- `apps/dsa-web/src/components/screening/ScreeningCompareTrayV104.tsx`
- `apps/dsa-web/src/components/screening/ScreeningReminderPanelV104.tsx`

### tests-and-verifiers

- `tests/test_market_screening_brief.py`
- `tests/test_auth_api.py`
- `tests/test_alphasift_api.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_platform_market_screening_alerts_v104_verifier.py`
- `scripts/verify_platform_market_screening_alerts_v104.py`
- `scripts/verify_platform_release_candidate_package.py`
- `apps/dsa-web/src/api/__tests__/alphasift.test.ts`
- `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`
- `apps/dsa-web/src/pages/__tests__/StockScreeningPage.test.tsx`
- `apps/dsa-web/src/components/screening/__tests__/screeningModelV104.test.ts`
- `apps/dsa-web/src/components/screening/__tests__/MarketScreeningCardV104.test.tsx`
- `apps/dsa-web/src/components/screening/__tests__/ScreeningCompareTrayV104.test.tsx`
- `apps/dsa-web/src/components/screening/__tests__/ScreeningReminderPanelV104.test.tsx`

### docs-and-config

- `.gitignore`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v104-explainable-stock-discovery.md`

Boundary: local-only, no real payment, no production keys, no production deployment, no investment advice. No `git add`, commit, or push is part of this slice.

## V105 Fast Useful Market Screening

### backend-platform-foundation

- `src/services/alphasift_screen_cache.py`
- `src/services/alphasift_service.py`
- `src/services/market_screening_brief.py`
- `api/v1/endpoints/alphasift.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/alphasift.ts`
- `apps/dsa-web/src/components/screening/screeningModelV104.ts`
- `apps/dsa-web/src/components/screening/MarketScreeningCardV104.tsx`
- `apps/dsa-web/src/pages/StockScreeningPage.tsx`

### tests-and-verifiers

- `tests/test_alphasift_screen_cache_v105.py`
- `tests/test_market_screening_brief.py`
- `tests/test_alphasift_api.py`
- `tests/test_platform_fast_useful_screening_v105_verifier.py`
- `apps/dsa-web/src/api/__tests__/alphasift.test.ts`
- `apps/dsa-web/src/components/screening/__tests__/screeningModelV104.test.ts`
- `apps/dsa-web/src/pages/__tests__/StockScreeningPage.test.tsx`
- `scripts/verify_platform_fast_useful_screening_v105.py`

### docs-and-config

- `.gitignore`
- `docs/superpowers/plans/2026-07-11-dsa-v105-fast-useful-market-screening.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

Boundary: local-only, no AI by default, no real payment, no production deployment, and no investment advice.

## V106 Financial Research Workflows

### backend-platform-foundation

- `api/middlewares/auth.py`
- `api/v1/endpoints/stocks.py`
- `api/v1/schemas/basic_query.py`
- `src/services/financial_research_workflow_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/components/layout/ShellHeader.tsx`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/i18n/uiText.ts`
- `apps/dsa-web/src/api/researchWorkflows.ts`
- `apps/dsa-web/src/pages/ResearchWorkflowsPage.tsx`

### tests-and-verifiers

- `apps/dsa-web/src/App.test.tsx`
- `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`
- `apps/dsa-web/src/api/__tests__/researchWorkflows.test.ts`
- `apps/dsa-web/src/pages/__tests__/ResearchWorkflowsPage.test.tsx`
- `tests/test_financial_research_workflow_service_v106.py`
- `tests/test_financial_research_workflow_api_v106.py`
- `tests/test_platform_financial_research_workflows_v106_verifier.py`
- `scripts/verify_platform_financial_research_workflows_v106.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

### docs-and-config

- `.env.example`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/github-feature-integrations-status.md`
- `docs/superpowers/plans/2026-07-11-dsa-v106-financial-research-workflows.md`
- `docs/superpowers/third-party/anthropic-financial-services.md`

### build-and-ignore-impact

- `.gitignore`

Boundary: the ignored external checkout is a read-only Apache-2.0 research-method reference. V106 executes no external agent or connector, consumes no AI quota, and provides information and data only.

## V107 Ollama Local AI Retention

### backend-platform-foundation

- `src/services/ollama_runtime_service.py`
- `src/services/analysis_service.py`
- `src/core/pipeline.py`
- `src/analyzer.py`
- `api/v1/endpoints/analysis.py`
- `api/v1/endpoints/platform.py`
- `api/middlewares/auth.py`
- `src/platform_feature_policy.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/components/retention/LocalModelStatusV107.tsx`

### tests-and-verifiers

- `tests/test_ollama_runtime_service_v107.py`
- `tests/test_platform_ollama_status_api_v107.py`
- `tests/test_platform_ollama_analysis_v107.py`
- `tests/test_platform_ollama_local_retention_v107_verifier.py`
- `apps/dsa-web/src/api/__tests__/platform.test.ts`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `apps/dsa-web/src/components/retention/__tests__/LocalModelStatusV107.test.tsx`
- `scripts/verify_platform_ollama_local_retention_v107.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`

### docs-and-config

- `.env.example`
- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/plans/2026-07-11-dsa-v107-ollama-local-retention.md`

Boundary: local Ollama only, no remote paid fallback, no production enablement, and information/data output only.

## Concurrent Product Research Notes

### manual-confirmation

- `docs/superpowers/plans/2026-07-11-dsa-api-membership-and-byok-conversation-notes.md`
- `docs/superpowers/plans/2026-07-11-dsa-membership-api-pricing-market-research.md`

These files appeared during V107 implementation and are classified for review coverage only. V107 does not adopt their pricing or production decisions.

## V112 Review Slice

### backend-platform-foundation

- `api/middlewares/auth.py`
- `api/v1/endpoints/__init__.py`
- `api/v1/endpoints/analysis.py`
- `api/v1/endpoints/billing.py`
- `api/v1/endpoints/local_connector.py`
- `api/v1/endpoints/platform.py`
- `api/v1/router.py`
- `api/v1/schemas/analysis.py`
- `api/v1/schemas/billing.py`
- `api/v1/schemas/local_connector.py`
- `api/v1/schemas/platform.py`
- `src/billing/lifecycle.py`
- `src/billing/payment_provider.py`
- `src/platform_accounts.py`
- `src/platform_feature_policy.py`
- `src/services/analysis_service.py`
- `src/services/api_boost_pack_service.py`
- `src/services/byok_routing_service.py`
- `src/services/member_model_catalog_service.py`
- `src/services/user_local_connector_service.py`
- `src/services/task_queue.py`
- `src/storage.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/analysis.ts`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/components/platform/BoostPackCardV112.tsx`
- `apps/dsa-web/src/components/platform/ModelConnectionWizardV112.tsx`
- `apps/dsa-web/src/components/platform/SimpleModelPickerV112.tsx`
- `apps/dsa-web/src/pages/AccountPage.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/types/analysis.ts`

### tests-and-verifiers

- `apps/dsa-web/src/components/platform/__tests__/BoostPackCardV112.test.tsx`
- `apps/dsa-web/src/components/platform/__tests__/ModelConnectionWizardV112.test.tsx`
- `apps/dsa-web/src/components/platform/__tests__/SimpleModelPickerV112.test.tsx`
- `apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_release_candidate_package.py`
- `scripts/verify_platform_simple_model_access_v112.py`
- `scripts/verify_platform_user_local_connector_live_v112.py`
- `tests/test_analysis_model_selection_v112.py`
- `tests/test_billing_subscription_lifecycle.py`
- `tests/test_local_connector_release_matrix_v112.py`
- `tests/test_member_model_catalog_v112.py`
- `tests/test_platform_api_keys_product.py`
- `tests/test_platform_boost_pack_v112.py`
- `tests/test_platform_simple_model_access_v112_verifier.py`
- `tests/test_user_local_connector_v112.py`

### docs-and-config

- `.env.example`
- `docs/CHANGELOG.md`
- `docs/superpowers/plans/2026-07-12-dsa-v112-api-boost-pack-simple-model-access.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

### build-and-ignore-impact

- `.gitignore`
- `.github/workflows/local-connector-release.yml`
- `apps/dsa-local-connector/app.py`
- `apps/dsa-local-connector/build-macos.sh`
- `apps/dsa-local-connector/build-windows.ps1`
- `apps/dsa-local-connector/client.py`
- `apps/dsa-local-connector/dsa-local-connector.spec`
- `apps/dsa-local-connector/ollama.py`
- `apps/dsa-local-connector/runtime.py`
- `apps/dsa-local-connector/requirements.txt`

Boundary: local sandbox only, no real key/payment, no investment advice, and no signed production artifact claim.

## Concurrent V113 Planning Artifact

### docs-and-config

- `docs/superpowers/plans/2026-07-12-dsa-v113-openstock-inspired-market-workspace.md`

This untracked planning file appeared during V112 implementation. It is preserved and classified for package coverage only; V112 does not claim that V113 was executed.

## V113 Review Slice

### backend-platform-foundation

- `api/middlewares/auth.py`
- `api/v1/endpoints/__init__.py`
- `api/v1/endpoints/market_workspace.py`
- `api/v1/router.py`
- `api/v1/schemas/market_workspace.py`
- `src/services/basic_query_service.py`
- `src/services/market_daily_brief_service.py`
- `src/services/market_search_service.py`
- `src/services/market_workspace_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/api/marketWorkspace.ts`
- `apps/dsa-web/src/components/layout/ShellHeader.tsx`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/components/market-workspace/GlobalStockCommandV113.tsx`
- `apps/dsa-web/src/components/market-workspace/MarketHeatmapV113.tsx`
- `apps/dsa-web/src/components/market-workspace/MarketMoversV113.tsx`
- `apps/dsa-web/src/components/market-workspace/MarketNewsTimelineV113.tsx`
- `apps/dsa-web/src/components/market-workspace/MarketPulseV113.tsx`
- `apps/dsa-web/src/components/market-workspace/SymbolWorkspaceV113.tsx`
- `apps/dsa-web/src/components/market-workspace/WatchlistBriefV113.tsx`
- `apps/dsa-web/src/i18n/uiText.ts`
- `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`

### tests-and-verifiers

- `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`
- `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`
- `scripts/verify_platform_market_workspace_v113.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_market_daily_brief_v113.py`
- `tests/test_market_search_v113.py`
- `tests/test_market_workspace_v113.py`
- `tests/test_platform_market_workspace_v113_verifier.py`

### docs-and-config

- `.env.example`
- `docs/superpowers/plans/2026-07-12-dsa-v113-openstock-inspired-market-workspace.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

### build-and-ignore-impact

- `.gitignore`

Boundary: DSA-native local implementation only; no OpenStock AGPL code copied, no real payment/key/deployment, and no investment advice.

## ai-market-pulse Isolated POC Review Slice

### docs-and-config

- `docs/superpowers/github-feature-integrations-status.md`
- `docs/superpowers/third-party/ai-market-pulse-poc.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

The ignored checkout under `external/ai-market-pulse` is local evidence only and is not part of the DSA release package. No upstream runtime is connected to DSA.

## V115 Unified Market Data Contract Review Slice

### Backend contract

- `src/services/market_data_contract.py`
- `src/services/basic_query_service.py`
- `api/v1/schemas/basic_query.py`

Review focus: freshness before source priority, deterministic tie-breaking, no averaging, field provenance, and URL/event deduplication.

### Frontend diagnostics

- `apps/dsa-web/src/api/stocks.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

Review focus: Chinese/English parity, compact data-credibility presentation, no secret values, and preserved information-only boundary.

### Tests, verifier, and docs

- `tests/test_market_data_contract_v115.py`
- `tests/test_platform_unified_market_data_v115_verifier.py`
- `scripts/verify_platform_unified_market_data_v115.py`
- `scripts/verify_platform_release_candidate_package.py`
- `docs/superpowers/plans/2026-07-12-dsa-v115-unified-market-data-contract.md`
- `docs/superpowers/github-feature-integrations-status.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `.gitignore`

Review focus: stable marker, Git visibility, dirty-file classification, no production/payment claim, and no changes to installed external source checkouts.

## Concurrent Hong Kong Market Research Review Slice

- `docs/superpowers/plans/2026-07-12-dsa-hong-kong-market-competitive-research.md`
- `docs/superpowers/plans/2026-07-12-dsa-hong-kong-market-simple-comparison.md`

These concurrent documents are inventoried without modifying their content. Review them separately before accepting any pricing, legal, market-data licensing or launch decision.

## V116 Public Market Home And Private Price Alerts

- `backend-platform-foundation`: V100 schema compatibility, exact-price rule service, public market aggregation, private worker/event APIs, config and schedule integration.
- `frontend-platform-experience`: public three-market home, shared price-alert form, private inbox, market deep-link and HomePage registration draft recovery.
- `tests-and-verifiers`: backend/unit/component/API tests, Playwright E2E and V116 verifier.
- `docs-and-config`: safe defaults, product rules, alerts boundary, local acceptance, changelog and V116 plan.
- `build-and-ignore-impact`: `.gitignore` only exposes the V116 verifier; no generated `static/` output is part of the source review.
- `manual-confirmation`: no requirements or production dependency change.

Review focus: no realtime or market-wide claim without authorization, first observation does not trigger, stale data does not trigger, A/B isolation, one schedule process, no secrets, and information-only copy.

## V117 Six Feature Experience Closure

- `backend-platform-foundation`: public history fallback, lightweight market overview/detail split, AlphaSift stale-cache fast path and Ollama test isolation.
- `frontend-platform-experience`: request-race guard, localized source/status/time/warnings, decision-journey source labels, chart sizing, guest stream suppression, screening session restore, and query-result-first collapse/expand behavior for market-home and guest account panels.
- `tests-and-verifiers`: focused backend/frontend regressions, V117 verifier and release-package coverage.
- `docs-and-config`: V117 plan, integration ledger, product rules, local acceptance, changelog and safe AlphaSift default.
- `build-and-ignore-impact`: `.gitignore` exposes only the V117 verifier; generated static assets remain ignored.

Review focus: six product capabilities are not six installed upstream runtimes, latest market request wins, no raw internal warning codes, no secret exposure, no investment advice, and no production claim.

## V118 Public Home Information Architecture

### backend-platform-foundation

- `api/v1/schemas/market_workspace.py`
- `api/v1/endpoints/market_workspace.py`
- `src/services/public_market_index_service.py`
- `src/services/public_market_news_service.py`
- `src/services/public_market_home_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/marketWorkspace.ts`
- `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- `apps/dsa-web/src/pages/AccountPage.tsx`
- `apps/dsa-web/src/pages/HomePage.tsx`

### tests-and-verifiers

- `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`
- `apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx`
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- `scripts/verify_platform_public_home_experience_v118.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_public_home_experience_v118_verifier.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_public_market_index_service_v118.py`
- `tests/test_public_market_news_service_v118.py`
- `tests/test_public_market_home_v116.py`

### docs-and-config

- `docs/CHANGELOG.md`
- `docs/superpowers/plans/2026-07-13-dsa-v118-public-home-information-architecture.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

### build-and-ignore-impact

- `.gitignore`

Review focus: allowlisted public web data may load automatically with bounded timeout and cache, model/API analysis must remain user-triggered, headline links retain attribution, account/model details stay off the default home, and no investment-advice or production claim is introduced.

## V119 Dynamic Market Home

### backend-platform-foundation

- `api/v1/endpoints/market_workspace.py`
- `api/v1/schemas/market_workspace.py`
- `src/services/public_market_home_service.py`
- `src/services/public_market_ranking_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/marketWorkspace.ts`
- `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- `apps/dsa-web/src/components/market-workspace/marketWorkspaceFormat.ts`

### tests-and-verifiers

- `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`
- `scripts/verify_platform_dynamic_market_home_v119.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_dynamic_market_home_v119_verifier.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_public_market_home_v116.py`
- `tests/test_public_market_ranking_service_v119.py`

### docs-and-config

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/plans/2026-07-14-dsa-v119-dynamic-market-home.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

Review focus: market-wide source mapping, liquidity filtering, no fixed-symbol fallback, bounded concurrency/cache, source freshness, bilingual labels, click-through query, no AI quota use, and no investment-advice claim.

## V120 Platform Support Center

### backend-platform-foundation

- `api/middlewares/auth.py`
- `api/v1/router.py`
- `api/v1/endpoints/support.py`
- `api/v1/schemas/support.py`
- `src/storage.py`
- `src/services/platform_support_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/api/support.ts`
- `apps/dsa-web/src/components/admin/SupportWorkbenchV120.tsx`
- `apps/dsa-web/src/components/layout/ShellHeader.tsx`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/i18n/uiText.ts`
- `apps/dsa-web/src/pages/AdminPage.tsx`
- `apps/dsa-web/src/pages/SupportPage.tsx`

### tests-and-verifiers

- `apps/dsa-web/e2e/platform-support-v120.spec.ts`
- `apps/dsa-web/src/App.test.tsx`
- `apps/dsa-web/src/api/__tests__/support.test.ts`
- `apps/dsa-web/src/components/admin/__tests__/SupportWorkbenchV120.test.tsx`
- `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`
- `apps/dsa-web/src/pages/__tests__/SupportPage.test.tsx`
- `scripts/verify_platform_release_candidate_package.py`
- `scripts/verify_platform_support_center_v120.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_platform_support_api_v120.py`
- `tests/test_platform_support_center_v120_verifier.py`

### docs-and-config

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/platform-support-center.md`
- `docs/superpowers/plans/2026-07-14-dsa-v120-platform-support-center.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

Review focus: user ownership isolation, administrator authorization, CSRF and rate limiting, closed-ticket behavior, bilateral unread semantics, audit metadata without message bodies, responsive bilingual UI, and no AI reply, attachment or investment-advice capability.

## V121 Free Market Stock Preview

### frontend-platform-experience

- `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- `apps/dsa-web/src/components/market-home/PublicMarketStockPreviewV121.tsx`

### tests-and-verifiers

- `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`
- `apps/dsa-web/src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx`
- `scripts/verify_platform_free_market_stock_preview_v121.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_free_market_stock_preview_v121_verifier.py`
- `tests/test_platform_release_candidate_package.py`

### docs-and-config

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/plans/2026-07-14-dsa-v121-free-market-stock-preview.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

Review focus: guest access, explicit on-demand loading, stale-request cancellation, useful public data depth, missing-field honesty, retry behavior, bilingual and mobile layout, no AI or paid quota consumption, and no investment-advice language.

## V122 Support Inbox Notifications

### backend-platform-foundation

- `api/v1/endpoints/support.py`
- `api/v1/schemas/support.py`
- `src/services/platform_support_service.py`

### frontend-platform-experience

- `apps/dsa-web/src/api/support.ts`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`

### tests-and-verifiers

- `apps/dsa-web/e2e/platform-support-notifications-v122.spec.ts`
- `apps/dsa-web/src/api/__tests__/support.test.ts`
- `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`
- `scripts/verify_platform_release_candidate_package.py`
- `scripts/verify_platform_support_notifications_v122.py`
- `tests/test_platform_release_candidate_package.py`
- `tests/test_platform_support_notifications_api_v122.py`
- `tests/test_platform_support_notifications_v122_verifier.py`

### docs-and-config

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/platform-support-center.md`
- `docs/superpowers/plans/2026-07-14-dsa-v122-support-inbox-notifications.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

Review focus: owner-scoped summaries, administrator authorization, redacted payloads, guest zero-request behavior, visible-only polling, immediate mutation refresh, accessible capped badges, desktop/mobile layout, and no AI or external notification channel.

## V124 Free Daily Market Workbench

### frontend-platform-experience

- `apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx`
- `apps/dsa-web/src/components/market-home/marketRecentV124.ts`
- `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`

### tests-and-verifiers

- `apps/dsa-web/src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx`
- `apps/dsa-web/src/components/market-home/__tests__/marketRecentV124.test.ts`
- `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`
- `scripts/verify_platform_free_daily_market_workbench_v124.py`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_free_daily_market_workbench_v124_verifier.py`
- `tests/test_platform_release_candidate_package.py`

### docs-and-config

- `.gitignore`
- `docs/CHANGELOG.md`
- `docs/superpowers/plans/2026-07-14-dsa-v124-free-daily-market-workbench.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`

Review focus: public-data reuse, no automatic model call, accurate published/observed/retrieved labels, browser-local recent research isolation, bilingual and mobile layout, click-through to the existing free query, and no investment-advice language.

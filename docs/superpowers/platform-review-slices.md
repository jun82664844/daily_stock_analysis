# DSA Platform Review Slices

Date: 2026-07-02

Scope: review slicing for the local V1/V2 platform release-candidate package. This is not a commit plan executed by the agent. Do not run `git add`, `git commit`, or `git push` until a human review owner explicitly approves the slice.

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

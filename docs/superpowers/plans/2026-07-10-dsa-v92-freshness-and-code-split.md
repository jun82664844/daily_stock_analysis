# DSA V92 Freshness Recovery And HomePage Code Split Implementation Plan

> **For Codex:** REQUIRED SUB-SKILL: Use executing-plans to implement this plan task-by-task.

**Goal:** Make free no-AI queries actively revalidate stale market-data cache entries while preserving a stale fallback, and reduce the initial HomePage JavaScript payload by lazy-loading conditional analysis/report surfaces.

**Architecture:** Keep the existing market routing, source health, cache, and diagnostics contracts. Change only stale-cache handling in `BasicQueryService`: fresh cache remains cache-first, stale cache triggers one live revalidation attempt, and failed or cooling-down sources fall back to the stale payload with explicit diagnostics. On the frontend, keep the existing HomePage behavior and component APIs but load report, task, history-trend, and run-flow surfaces only when their UI branch is rendered.

**Tech Stack:** Python 3.11, FastAPI service layer, `unittest`, React 19, TypeScript, Vite, Vitest, Playwright.

---

## Track A: Free Market-Data Freshness

### Task 1: Lock stale-revalidation behavior with failing tests

**Files:**
- Create: `tests/test_platform_market_data_freshness_v92.py`
- Modify: `tests/test_platform_query_quality_v4.py`

1. Add deterministic tests proving a fresh cache hit avoids the live source.
2. Add tests proving stale quote, history, and profile cache entries trigger live revalidation and return fresh payloads when the source succeeds.
3. Add tests proving timeout, empty response, error, and source cooldown return the stale payload instead of losing usable data.
4. Assert diagnostics distinguish `revalidated` from `stale_fallback` and never claim AI usage.
5. Run the focused tests and confirm they fail for the missing stale-revalidation behavior.

### Task 2: Implement stale-while-revalidate service behavior

**Files:**
- Modify: `src/services/basic_query_service.py`

1. Preserve immediate returns for fresh memory and disk cache hits.
2. Retain stale entries as fallback candidates and attempt the configured live source once.
3. On live success, replace cache data and report a `revalidated` cache state.
4. On timeout, source error, empty response, or cooldown, return the stale entry with `stale_fallback` diagnostics and the real source-health/error state.
5. Run the V92 freshness tests and relevant V4/V22 regressions.

## Track B: HomePage Initial Payload

### Task 3: Add a failing bundle-size acceptance check

**Files:**
- Create: `apps/dsa-web/scripts/verify-homepage-bundle-v92.mjs`
- Modify: `apps/dsa-web/package.json`

1. Inspect the built `static/assets/HomePage-*.js` entry.
2. Fail when the largest HomePage entry exceeds 500 KiB.
3. Require at least one independently emitted lazy feature chunk.
4. Run the verifier against the V91 build and confirm the size check fails.

### Task 4: Lazy-load conditional HomePage feature surfaces

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify tests only where asynchronous lazy rendering requires it.

1. Replace static imports for conditional report, task, history-trend, markdown, and run-flow surfaces with typed `React.lazy` imports.
2. Wrap each conditional boundary in a stable `Suspense` fallback that does not shift the layout.
3. Preserve existing props, callbacks, accessibility labels, translations, and user flows.
4. Run focused HomePage tests, TypeScript, production build, and the V92 bundle verifier.

## Track C: Integrated Local Acceptance

### Task 5: Verify, review, and close V92 cleanly

**Files:**
- Modify documentation only if implementation evidence changes the stated boundary.

1. Run backend freshness and platform query regressions.
2. Run frontend HomePage/decision journey tests, TypeScript, build, and bundle verifier.
3. Run the local V1 operability gate and check `http://127.0.0.1:8018/health`.
4. Restart 8018 if required, then browser-test A-share, US, Hong Kong, and crypto queries on desktop and mobile.
5. Verify stale-source failures remain visible and no result is presented as real-time when it is not.
6. Review the diff for regressions, secrets, destructive operations, and scope creep.
7. Commit the V92 work locally without pushing and confirm the final worktree is clean.

**Boundaries:** No production deployment, real payment, production secrets, real merchant integration, DNS, HTTPS/WAF, public search enablement, user-data deletion, or investment-advice claims.

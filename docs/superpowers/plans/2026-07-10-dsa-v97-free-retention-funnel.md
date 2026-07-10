# DSA V97 Free Retention Funnel Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Record the five local free-user conversion stages and show administrators a privacy-bounded funnel with unique-session counts and conversion rates.

**Architecture:** Reuse `platform_audit_events` as the local event ledger. A public, rate-limited endpoint accepts only five fixed event names, hashes the browser session id before persistence, rejects arbitrary metadata, and attaches the authenticated user id when available. An admin-only endpoint calculates a monotonic cohort funnel for a bounded time window; the frontend sends events best-effort and renders the summary without blocking stock queries.

**Tech Stack:** FastAPI, Pydantic, SQLAlchemy-backed platform audit storage, React, TypeScript, Vitest, Playwright.

---

### Task 1: Retention event service and API

**Files:**
- Create: `src/platform_retention_funnel.py`
- Modify: `api/v1/schemas/platform.py`
- Modify: `api/v1/endpoints/platform.py`
- Test: `tests/test_platform_retention_funnel_v97.py`

- [ ] Write failing tests proving the public endpoint accepts only `free_query_completed`, `registration_completed`, `api_trial_submitted`, `trial_report_opened`, and `premium_options_viewed`.
- [ ] Run `python -m unittest -q tests.test_platform_retention_funnel_v97` and confirm missing service/routes fail.
- [ ] Implement session-id hashing, fixed source validation, same-day duplicate suppression, optional authenticated user ownership, and no arbitrary metadata persistence.
- [ ] Implement the admin-only 30-day summary with raw unique sessions, reached-from-start sessions, previous-stage conversion, and start-stage conversion.
- [ ] Re-run the backend test and confirm normal users receive `403` for the admin summary.

### Task 2: Browser session and typed API

**Files:**
- Create: `apps/dsa-web/src/utils/retentionFunnel.ts`
- Create: `apps/dsa-web/src/utils/__tests__/retentionFunnel.test.ts`
- Modify: `apps/dsa-web/src/api/platform.ts`

- [ ] Write a failing Vitest contract for stable local session creation, reuse, and restricted-storage fallback.
- [ ] Run the test and confirm the helper is missing.
- [ ] Implement a versioned local-storage session id with `crypto.randomUUID()` and a non-secret in-memory fallback.
- [ ] Add typed `trackRetentionEvent` and `adminRetentionFunnel` API methods.
- [ ] Re-run the helper test.

### Task 3: Five-stage HomePage instrumentation

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/e2e/platform-user-e2e.spec.ts`

- [ ] Extend the browser E2E mock and assertions so a complete free trial journey records the five event names in order.
- [ ] Run the focused Playwright test and confirm it fails because tracking calls are absent.
- [ ] Add one best-effort tracker callback that never blocks or fails a stock query.
- [ ] Emit events only after successful no-AI query, successful registration, accepted platform trial, automatic report opening, and premium-options click.
- [ ] Re-run the focused Playwright flow and confirm the report and account navigation still work.

### Task 4: Admin conversion panel

**Files:**
- Create: `apps/dsa-web/src/components/admin/RetentionFunnelPanelV97.tsx`
- Create: `apps/dsa-web/src/components/admin/__tests__/RetentionFunnelPanelV97.test.tsx`
- Modify: `apps/dsa-web/src/pages/AdminPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`

- [ ] Write failing component/AdminPage tests for Chinese and English labels, five stages, unique counts, conversion rates, window text, and local-only/no-AI copy.
- [ ] Implement a compact unframed funnel panel with stable responsive columns and no secret/session identifiers.
- [ ] Load the admin summary with existing admin data and preserve refresh/error behavior.
- [ ] Re-run AdminPage and panel tests.

### Task 5: Documentation and acceptance

**Files:**
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] Document the five-event whitelist, hashing, deduplication, admin-only summary, and local-only privacy boundary.
- [ ] Run targeted backend and frontend suites, all three platform Playwright journeys, and `npm run build`.
- [ ] Run release-package, local-operability, V2-readiness, `git diff --check`, live `8018` hash/health, and dirty-tree classification.

Rollback: revert the V97 service, endpoints, frontend tracker/panel, event calls, tests, and V97 docs together. Do not delete audit history, reports, databases, cache files, or user data.

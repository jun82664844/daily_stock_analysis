# DSA Local Market Recovery Console V13 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only Admin recovery console for resetting quick-query source cooldown state and optionally no-AI prewarming the default market smoke symbols.

**Architecture:** Keep V11 source-health snapshot and V12 prewarm as the source of truth. Add a narrow admin-only recovery API that resets selected in-memory source-health states and optionally calls the existing no-AI prewarm path; then expose it from AdminPage with a compact recovery result summary.

**Tech Stack:** FastAPI, Pydantic, in-memory market source health registry, React/Vite, Vitest, Python unittest verifiers.

---

## Scope

- Local-only operator tooling.
- No production deployment, real payment, real API Key handoff, public SearXNG enablement, or investment-advice claim.
- No deletion of reports, history, user records, databases, or static build output.
- No disk-cache purge in this stage; cache recovery is performed by no-AI prewarm refresh, not destructive cache deletion.

## Files

- Create: `docs/superpowers/plans/2026-07-03-dsa-local-v13-market-recovery-console.md`
- Create: `tests/test_platform_local_market_recovery_console_v13.py`
- Create: `scripts/verify_platform_local_market_recovery_console_v13.py`
- Modify: `src/services/market_source_health.py`
- Modify: `src/services/market_source_ops.py`
- Modify: `api/v1/schemas/basic_query.py`
- Modify: `api/v1/endpoints/stocks.py`
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/pages/AdminPage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/AdminPage.test.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

## Tasks

### Task 1: Backend Recovery Contract

- [ ] Write failing unittest for resetting only selected source-health entries.
- [ ] Add `MarketSourceHealthRegistry.reset_sources()`.
- [ ] Add `recover_market_sources()` in `market_source_ops.py`.
- [ ] Verify the unittest passes.

### Task 2: Admin-Only Recovery API

- [ ] Write failing API test showing ordinary platform users receive 403.
- [ ] Add request/response schemas.
- [ ] Add `POST /api/v1/stocks/sources/recovery` guarded by admin identity.
- [ ] Verify the API test passes and response keeps `ai_used=false`.

### Task 3: AdminPage Recovery UX

- [ ] Write failing AdminPage test for `Recover local sources`.
- [ ] Add `stocksApi.recoverMarketSources()`.
- [ ] Add AdminPage recovery state, button, result summary, and source-health refresh.
- [ ] Verify frontend tests pass.

### Task 4: V13 Verifier And Package Docs

- [ ] Add `scripts/verify_platform_local_market_recovery_console_v13.py`.
- [ ] Add `.gitignore` exception and release-package coverage.
- [ ] Update local acceptance, review slices, and release manifest.
- [ ] Run V13 verifier, release verifier, local V1, V2, frontend build, and `git diff --check`.

## Acceptance

- `scripts/verify_platform_local_market_recovery_console_v13.py` prints `DSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK`.
- Admin recovery action is admin-only.
- Recovery resets source-health cooldown without clearing user data or historical reports.
- Optional prewarm uses existing no-AI path and returns `ai_used=false`.
- Dirty tree is reported after completion.

# DSA V59 A-Stock-Data POC Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local-only A-share enrichment lane inspired by `a-stock-data`, so free quick queries can show richer A-share context without AI calls or production/payment scope.

**Architecture:** Keep the current no-AI quick snapshot as the entry point. Add a small backend adapter that returns cached/degraded enrichment channels for A-share symbols only, then expose those channels through `BasicStockSnapshot.intelligence` and render them in `HomePage`.

**Tech Stack:** FastAPI, Pydantic, Python unittest, React, TypeScript, Vitest, local JSON market cache.

---

### Task 1: Backend Contract

**Files:**
- Modify: `api/v1/schemas/basic_query.py`
- Modify: `tests/test_basic_query_no_ai.py`

- [ ] **Step 1: Write the failing test**

Add a test that calls `BasicQueryService(...).get_snapshot("600519")` with a fake A-share stock service and fake enrichment service, then asserts:
- `intelligence.a_share_enrichment` exists for A-share symbols.
- It contains `announcements`, `capital_flow`, `sector`, `research`, and `dragon_tiger` channels.
- `ai_used` and `public_search_used` are false.
- The source and boundary clearly say local-only information analysis, not investment advice.

- [ ] **Step 2: Run test to verify it fails**

Run:

```powershell
C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe -m unittest tests.test_basic_query_no_ai.BasicQueryNoAiTestCase.test_a_share_snapshot_includes_a_stock_data_enrichment_poc
```

Expected: FAIL because `a_share_enrichment` does not exist.

- [ ] **Step 3: Add schema models**

Add `BasicAShareEnrichmentChannelPayload` and `BasicAShareEnrichmentPayload`, then add optional `a_share_enrichment` to `BasicIntelligencePayload`.

- [ ] **Step 4: Re-run the test**

Expected: still FAIL until the service populates the field.

### Task 2: Local Adapter

**Files:**
- Create: `src/services/a_share_enrichment_service.py`
- Modify: `src/services/basic_query_service.py`
- Test: `tests/test_basic_query_no_ai.py`

- [ ] **Step 1: Write minimal adapter tests**

Test that the adapter normalizes `600519.SH` to `600519`, returns five channels from fixture data, and degrades safely when the HTTP client raises.

- [ ] **Step 2: Run adapter tests to verify RED**

Expected: FAIL because the service file does not exist.

- [ ] **Step 3: Implement adapter**

Implement a small local-only service with:
- `get_enrichment(stock_code, stock_name=None, profile=None, quote=None)`
- dependency-injected `http_get`
- short timeout
- local summaries for announcements, capital flow, sector, research, dragon-tiger
- no AI calls and no public search
- safe degraded payload when upstream fails

- [ ] **Step 4: Wire it into `BasicQueryService`**

Inject optional `a_share_enrichment_service`; call it only when `route.market == "cn"`; never call it for US/HK/crypto.

### Task 3: Frontend API And UI

**Files:**
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: Write frontend failing tests**

Add API mapping assertions for `a_share_enrichment -> aShareEnrichment`. Add HomePage assertions for the Chinese A-share enrichment panel.

- [ ] **Step 2: Run tests to verify RED**

Expected: FAIL because the type and UI do not exist.

- [ ] **Step 3: Implement TypeScript types and UI**

Render a compact panel titled `A股增强数据` / `A-share enrichment`, with five channel cards and labels for source, status, and boundary.

### Task 4: Verification And Packaging

**Files:**
- Create: `scripts/verify_platform_a_stock_data_poc_v59.py`
- Create: `tests/test_platform_a_stock_data_poc_v59.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`

- [ ] **Step 1: Add verifier tests**

Check that backend, frontend, tests, plan, no-AI markers, and local-only boundary are present.

- [ ] **Step 2: Run verifier tests and targeted suites**

Run backend unittest, frontend Vitest, build, V59 verifier, release package verifier, and `git diff --check`.

- [ ] **Step 3: Commit**

Stage only V59 files and commit:

```powershell
git add -- <explicit files>
git commit -m "feat: add a-share enrichment poc"
```

### Local Acceptance Boundary

Status marker: `DSA_PLATFORM_A_STOCK_DATA_POC_V59_OK`

This stage is local-only. It does not enable real payment, production deployment, public SearXNG, real API keys, or production data-source licensing. The A-share enrichment lane must remain no-AI by default, must not use public search in quick mode, must degrade instead of blocking the quick snapshot, and all output remains information analysis only; not investment advice. Do not commit real API Key.

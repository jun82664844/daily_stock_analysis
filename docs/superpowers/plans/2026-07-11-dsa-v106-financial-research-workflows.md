# DSA V106 Financial Research Workflows Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Install the Anthropic financial-services source as an isolated local reference and expose four neutral, no-AI research workflows powered by DSA market data.

**Architecture:** Clone the external Apache-2.0 repository under an ignored `external/` directory and never import or execute its agents, scripts, commands, or MCP connectors. A DSA-owned allowlist maps four research methods to deterministic facts from the existing stock snapshot API, while a public bilingual research page renders provenance, missing-data states, and an information-only boundary.

**Tech Stack:** Python 3.12, FastAPI, Pydantic, React, TypeScript, Vitest, unittest, Playwright.

---

### Task 1: Isolated source installation

**Files:**
- Modify: `.gitignore`
- Create: `docs/superpowers/third-party/anthropic-financial-services.md`
- Test: `tests/test_financial_research_workflow_service_v106.py`

- [ ] Add a failing test that requires source diagnostics to report the repository, license, commit, and the four allowlisted workflows without executing external code.
- [ ] Clone `https://github.com/anthropics/financial-services.git` into `external/anthropic-financial-services` with a shallow checkout.
- [ ] Ignore the external checkout and document its Apache-2.0 attribution, update procedure, disabled connectors, and rollback path.
- [ ] Run the focused backend test and confirm the source diagnostics pass.

### Task 2: Deterministic research workflow backend

**Files:**
- Create: `src/services/financial_research_workflow_service.py`
- Modify: `api/v1/endpoints/stocks.py`
- Modify: `api/v1/schemas/basic_query.py`
- Test: `tests/test_financial_research_workflow_service_v106.py`
- Test: `tests/test_financial_research_workflow_api_v106.py`

- [ ] Add failing tests for company snapshot, earnings review, sector overview, and catalyst calendar contracts.
- [ ] Require `ai_used=false`, `public_search_used=false`, neutral factual wording, source freshness, missing-data reasons, and an information-only boundary.
- [ ] Add `GET /api/v1/stocks/{stock_code}/research-workflows` using the existing `BasicQueryService` snapshot and no external connector calls.
- [ ] Run service and API tests until green.

### Task 3: Public bilingual research center

**Files:**
- Create: `apps/dsa-web/src/api/researchWorkflows.ts`
- Create: `apps/dsa-web/src/pages/ResearchWorkflowsPage.tsx`
- Create: `apps/dsa-web/src/pages/__tests__/ResearchWorkflowsPage.test.tsx`
- Create: `apps/dsa-web/src/api/__tests__/researchWorkflows.test.ts`
- Modify: `apps/dsa-web/src/App.tsx`
- Modify: `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`

- [ ] Add failing API and page tests covering anonymous access, four workflows, provenance, missing-data display, and Chinese/English copy.
- [ ] Implement a compact `/research` page with a stock-code input, factual workflow cards, source status, and no-AI/information-only labels.
- [ ] Add a visible sidebar route named `研究中心` / `Research center`.
- [ ] Run focused Vitest and production build until green.

### Task 4: Release and safety gates

**Files:**
- Create: `scripts/verify_platform_financial_research_workflows_v106.py`
- Create: `tests/test_platform_financial_research_workflows_v106_verifier.py`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/CHANGELOG.md`

- [ ] Add a failing verifier test requiring source attribution, disabled connectors, no-AI contract, backend tests, and frontend tests.
- [ ] Implement the V106 verifier and release-package coverage.
- [ ] Record that the external source is a reference workflow library, not a market-data license, investment recommendation engine, or production connector approval.
- [ ] Run the V106 verifier and release-package verifier.

### Task 5: Live acceptance and Git closure

- [ ] Restart the local service from the E-drive project and verify `/health`.
- [ ] Verify anonymous Chinese and English `/research` flows in the browser with at least one A-share and one US symbol.
- [ ] Confirm no browser console errors, no exposed secrets, and no investment-advice wording.
- [ ] Run `git diff --check`, explicit sensitive-data scans, and review all dirty files.
- [ ] Stage only the validated V106 files, commit locally, do not push, and confirm `git status --short --untracked-files=all` is empty.

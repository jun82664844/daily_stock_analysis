# DSA V103 Free Daily Research Cockpit Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the existing private watchlist radar into a concise daily research cockpit that gives free users a reason to return without consuming AI quota.

**Architecture:** Reuse V99/V100 watchlist refresh, persisted radar runs, alert rules, source-health evidence, and existing free API trial quota. Add a deterministic research-brief layer to each radar item and aggregate it into three daily groups; render a compact bilingual cockpit before the detailed radar, with drill-down into the existing stock page and optional API trial.

**Tech Stack:** Python 3, FastAPI/Pydantic, React/TypeScript, Vitest, Playwright, unittest, existing DSA verifier and release-package stack.

---

### Task 1: Lock the deterministic research brief contract

**Files:**
- Create: `tests/test_platform_daily_research_cockpit_v103.py`
- Modify: `src/platform_watchlist_radar.py`
- Modify: `api/v1/schemas/platform.py`

- [ ] Add failing tests for strong-confirmation, risk-review, and wait-for-confirmation classification.
- [ ] Require structured evidence codes, next-watch trigger, invalidation condition, priority score, and data-confidence level without generated advice text.
- [ ] Require daily group summaries, top-three limits, freshness counts, `ai_used=false`, and unchanged free/pro watchlist limits.
- [ ] Implement the smallest deterministic classifier and stable ranking needed to pass.
- [ ] Confirm stale or unavailable data can never enter strong-confirmation and remains visibly low-confidence.

### Task 2: Expose the cockpit through the existing radar API

**Files:**
- Modify: `api/v1/schemas/platform.py`
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `tests/test_platform_watchlist_event_radar_v99.py`
- Modify: `apps/dsa-web/src/api/__tests__/platform.test.ts`

- [ ] Add typed snake-case and camel-case contracts for item research briefs and the daily digest.
- [ ] Prove the authenticated endpoint returns only the current user's watchlist summary.
- [ ] Prove no API key, raw provider error, AI output, or public-search output is exposed.

### Task 3: Build the bilingual free daily cockpit

**Files:**
- Create: `apps/dsa-web/src/components/radar/DailyResearchCockpitV103.tsx`
- Create: `apps/dsa-web/src/components/radar/__tests__/DailyResearchCockpitV103.test.tsx`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] Write failing component tests for Chinese and English group labels, evidence, data confidence, trial quota, and symbol drill-down.
- [ ] Render three compact groups before V100/V99 detail, without nesting cards or hiding degraded data.
- [ ] Show the remaining weekly platform API trial count and route users to the selected stock page without consuming quota automatically.
- [ ] Keep all text inside responsive containers at desktop and mobile widths.

### Task 4: Add V103 machine-checkable acceptance

**Files:**
- Create: `scripts/verify_platform_free_daily_research_cockpit_v103.py`
- Create: `tests/test_platform_free_daily_research_cockpit_v103_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] Make the verifier run focused backend and frontend tests and emit `DSA_PLATFORM_FREE_DAILY_RESEARCH_COCKPIT_V103_OK` only after all gates pass.
- [ ] Keep the verifier visible to Git and classify every V103 dirty file in the release package.
- [ ] Document local-only, no-AI, source-freshness, optional API-trial, and not-investment-advice boundaries.

### Task 5: Full local and browser acceptance

**Files:**
- Verify only; do not delete reports, databases, watchlists, users, or API-key records.

- [ ] Run focused backend tests, frontend tests, lint, build, V103 verifier, release-package verifier, and existing V99/V100/V102 gates.
- [ ] Restart only the confirmed DSA listener on 8018 after code verification.
- [ ] In a fresh browser, run the daily review for a free user and verify the three groups, data-confidence labels, trial quota, symbol drill-down, Chinese/English parity, and no failure banner.
- [ ] Explicitly stage only V103 files, create one local commit, do not push, and confirm a clean worktree plus healthy 8018 service.

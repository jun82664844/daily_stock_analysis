# DSA V73 Free Broker Conversion Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Rebuild the free query result first screen into a broker-style decision cockpit that makes ordinary visitors understand the value quickly and consider upgrading for steadier API/model sources.

**Architecture:** Keep the current free and premium visible modules aligned. Add a new free broker cockpit inside `HomePage` above the existing commercial journey, using the already-loaded no-AI snapshot data instead of adding a new backend dependency.

**Tech Stack:** React, TypeScript, Vitest, local FastAPI service, existing DSA verifier scripts.

---

### Task 1: Lock The Broker Conversion Contract

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add a focused test that checks for `basic-query-broker-cockpit`, Chinese copy for `经纪人首屏研判`, `现在值不值得继续看`, `升级后解决什么`, `证据链`, `风险边界`, and the not-investment-advice boundary.

- [x] **Step 2: Run test to verify it fails**

Run: `npm run test -- --run src/pages/__tests__/HomePage.test.tsx -t "renders broker-style free conversion cockpit"`

Expected: FAIL because `basic-query-broker-cockpit` does not exist yet.

### Task 2: Implement The First-Screen Broker Cockpit

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add view-model data**

Create a small local view model derived from `basicSnapshot`: verdict, proof chain, risk boundary, upgrade reasons, and next action labels. Use existing quote, profile, signal score, comparison targets, and freshness fields.

Keep the user-facing boundary explicit: this is not investment advice.

- [x] **Step 2: Render before the current commercial journey**

Render the cockpit immediately after `basic-query-primary-summary`, before `basic-query-commercial-journey`, so the first screen answers the user before asking them to scroll.

- [x] **Step 3: Keep free/premium parity**

Copy must say free users see the same research structure, while premium/API improves source stability, real-time links, and model depth.

### Task 3: Add Static Verifier Coverage

**Files:**
- Create: `scripts/verify_platform_free_broker_conversion_v73.py`
- Create: `tests/test_platform_free_broker_conversion_v73.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`

- [x] **Step 1: Add verifier**

Verifier must require `basic-query-broker-cockpit`, the broker Chinese copy, the upgrade copy, a browser test assertion, and this plan file.

- [x] **Step 2: Wire release package**

Make the V73 verifier visible to Git and included in the release-candidate manifest/review slices.

### Task 4: Verify And Commit

**Files:**
- All files above

- [x] **Step 1: Run targeted tests**

Run backend verifier tests and HomePage Vitest.

- [x] **Step 2: Build and live-check**

Run `npm run build`, restart 8018 if needed, and use browser automation to query AAPL and confirm the cockpit is visible.

- [x] **Step 3: Commit only the V73 slice**

Run `git diff --check`, staged secret scan, commit locally, and confirm `git status -sb --untracked-files=all` is clean.

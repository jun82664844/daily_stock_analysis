# DSA V91 Decision Journey Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the free quick-analysis result into a focused, evidence-backed decision journey that works for A-share, US, Hong Kong, and crypto symbols while reducing `HomePage.tsx` growth.

**Architecture:** Add a focused `DecisionJourneyV91` presentation component and a pure market-model builder. `HomePage` continues to own requests and account state, but passes one normalized view model into the extracted component. Existing lower V86-V88 modules remain available as secondary evidence, while the duplicated V89/V90 first-screen blocks are replaced by V91.

**Tech Stack:** React 18, TypeScript, Tailwind CSS, Vitest, Testing Library, Vite, existing DSA basic snapshot API.

---

### Task 1: Lock the V91 decision model with failing tests

**Files:**
- Create: `apps/dsa-web/src/components/analysis/__tests__/decisionJourneyModel.test.ts`
- Create: `apps/dsa-web/src/components/analysis/decisionJourneyModel.ts`

- [x] **Step 1: Write failing tests for four market templates and technical evidence**

Test that `buildDecisionJourneyModel` returns localized market focus labels for `cn`, `us`, `hk`, and `crypto`, derives MA/RSI evidence from trend points, and preserves source/freshness metadata.

- [x] **Step 2: Run the model test and verify RED**

Run: `npm.cmd run test -- --run src/components/analysis/__tests__/decisionJourneyModel.test.ts`

Expected: FAIL because `decisionJourneyModel.ts` does not exist.

- [x] **Step 3: Implement the pure decision model**

Create a typed builder that accepts `BasicStockSnapshot`, language, conclusion, score, risk, support, and resistance. It must return conclusion/evidence/risk/upgrade cards, a compact price-series model, technical metrics, market-specific focus items, source trust fields, and truthful free/premium boundaries.

- [x] **Step 4: Run the model test and verify GREEN**

Run: `npm.cmd run test -- --run src/components/analysis/__tests__/decisionJourneyModel.test.ts`

Expected: all model tests PASS.

### Task 2: Build the extracted V91 decision journey

**Files:**
- Create: `apps/dsa-web/src/components/analysis/DecisionJourneyV91.tsx`
- Create: `apps/dsa-web/src/components/analysis/__tests__/DecisionJourneyV91.test.tsx`

- [x] **Step 1: Write failing component tests**

Test the first-screen conclusion, evidence tabs, market focus, price chart, source/freshness disclosure, free/premium comparison, Chinese/English rendering, and jump callbacks. Confirm tab changes never call an AI action.

- [x] **Step 2: Run the component test and verify RED**

Run: `npm.cmd run test -- --run src/components/analysis/__tests__/DecisionJourneyV91.test.tsx`

Expected: FAIL because `DecisionJourneyV91.tsx` does not exist.

- [x] **Step 3: Implement the component**

Render a compact professional first screen followed by a tabbed evidence library. Use the repository Button component and Lucide icons. Keep cards at 8px radius or less, avoid nested cards, keep mobile text inside its bounds, and show the information-analysis disclaimer.

- [x] **Step 4: Run the component test and verify GREEN**

Run: `npm.cmd run test -- --run src/components/analysis/__tests__/DecisionJourneyV91.test.tsx`

Expected: all component tests PASS.

### Task 3: Integrate V91 and remove first-screen duplication

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Change the HomePage integration test to the desired V91 behavior**

Replace V89/V90 first-screen assertions with V91 assertions. Verify V91 follows the quick-mode banner, contains one first-screen decision surface, exposes the evidence tabs, keeps V86-V88 as secondary evidence, and does not invoke AI.

- [x] **Step 2: Run the HomePage test and verify RED**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx`

Expected: FAIL because V91 is not integrated.

- [x] **Step 3: Integrate the model/component and remove duplicated V89/V90 render blocks**

Build the V91 view model with `useMemo`, render `DecisionJourneyV91` after the quick-mode banner, wire evidence/upgrade jump targets, remove the obsolete V89/V90 view-model/render code, and retain the lower evidence modules.

- [x] **Step 4: Run the HomePage test and verify GREEN**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx`

Expected: all HomePage tests PASS.

### Task 4: Verify local behavior and package quality

**Files:**
- Modify only if verification reveals a confirmed defect.

- [x] **Step 1: Run focused frontend tests**

Run: `npm.cmd run test -- --run src/components/analysis/__tests__/decisionJourneyModel.test.ts src/components/analysis/__tests__/DecisionJourneyV91.test.tsx src/pages/__tests__/HomePage.test.tsx`

Expected: all tests PASS with zero failures.

- [x] **Step 2: Run type and build gates**

Run: `npx.cmd tsc --noEmit -p tsconfig.app.json`

Run: `npm.cmd run build`

Expected: exit code 0. Record any remaining chunk-size warning honestly.

- [x] **Step 3: Run local operability and whitespace checks**

Run: `..\dsa-venv\Scripts\python.exe scripts\verify_local_v1_operability.py`

Run: `git diff --check`

Expected: operability gates PASS and no whitespace errors.

- [x] **Step 4: Browser acceptance**

Open `http://127.0.0.1:8018/?dsa_v91_smoke=1`. Verify guest quick analysis for `AAPL`, `600519.SH`, `00700.HK`, and `BTC-USD`; verify V91 Chinese/English labels, evidence-tab switching, source freshness, and no login requirement for query.

- [x] **Step 5: Inline code review and closure**

Review the complete diff for correctness, market-label leakage, localization gaps, secret exposure, duplicated first-screen content, and mobile overflow. Fix critical/important findings, rerun affected checks, commit explicit V91 files, and confirm `git status --short --untracked-files=all` is empty.

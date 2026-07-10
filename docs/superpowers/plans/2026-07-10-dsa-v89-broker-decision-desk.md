# DSA V89 Broker Decision Desk Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the free quick-analysis page feel like a useful broker workstation by moving the decision, opportunity, risk, evidence, and premium-upgrade explanation into the first quick-analysis screen.

**Architecture:** Reuse the existing no-AI `basicSnapshot`, `basicFreeReport`, `basicBrokerCockpit`, and jump handlers. Add a new V89 decision desk section immediately after the quick-analysis mode banner, before the older workflow cards, so the user sees a concise decision layer before scrolling into detailed modules.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA quick snapshot UI.

---

### Task 1: Add Failing Decision Desk Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions in the no-AI quick-query test after `basic-query-mode-banner`:
- `basic-query-broker-decision-desk-v89` exists
- appears before `basic-query-next-actions-v85`
- shows `经纪人决策台`
- shows `先给结论`
- shows `机会窗口`
- shows `风险边界`
- shows `证据确认`
- shows `高级版补强`
- shows `免费版看到同样结构`
- shows `未用 AI，不扣额度`
- shows `仅作信息分析，不构成投资建议`
- clicking `看证据`, `看风险`, and `看升级差异` must not call `analysisApi.analyzeAsync`

- [x] **Step 2: Run the test to verify it fails**

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-broker-decision-desk-v89` does not exist yet.

### Task 2: Implement Decision Desk

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add decision desk data model**

Create `basicBrokerDecisionDesk` from `basicSnapshot`, `basicFreeReport`, and `basicBrokerCockpit`. It should include localized title, conclusion, opportunity, risk, evidence, upgrade copy, and action labels.

- [x] **Step 2: Render V89 section near the top**

Render `data-testid="basic-query-broker-decision-desk-v89"` in quick mode immediately after `basic-query-mode-banner` and before `basic-query-next-actions-v85`.

- [x] **Step 3: Keep it no-AI and navigation-only**

The `看证据`, `看风险`, and `看升级差异` buttons should only jump to existing local sections and must not call AI analysis.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-10-dsa-v89-broker-decision-desk.md`

- [x] **Step 1: Run target tests**

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

- [x] **Step 2: Run build and local gates**

```powershell
npx tsc --noEmit -p tsconfig.app.json
npm run build
python scripts\verify_local_v1_operability.py
git diff --check
```

- [x] **Step 3: Browser smoke**

Open `http://127.0.0.1:8018/?dsa_v89_smoke=1`, query `AAPL`, open quick analysis, confirm the V89 decision desk appears near the top, and confirm its navigation buttons reach existing sections.

- [x] **Step 4: Commit cleanly**

Commit only V89 files and finish with a clean working tree.

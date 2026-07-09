# DSA V86 Free Analyst Workbench Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the free quick-analysis result feel like a useful analyst workbench, not just a list of quote fields.

**Architecture:** Add a top-of-result V86 workbench card in `HomePage.tsx`, driven by the existing no-AI quick snapshot and free report data. The card summarizes whether the stock is worth continuing to read, the main reason, biggest risk, concrete next path, and free-vs-premium value, while preserving the same feature access for free users.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing DSA quick snapshot UI.

---

### Task 1: Add Failing Workbench Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions after the V85 next-actions card:
- `basic-query-free-analyst-workbench-v86` exists
- shows `免费研判工作台`
- shows `像经纪人一样先看结论、证据、风险和下一步`
- shows `是否值得继续看`
- shows `当前最大看点`
- shows `最大风险`
- shows `下一步路径`
- shows `免费版已经开放`
- shows `高级版增强`
- shows `未用 AI，不扣额度`
- clicking `看资讯` and `看K线` does not call `analysisApi.analyzeAsync`

- [x] **Step 2: Run the test to verify it fails**

Run:

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-free-analyst-workbench-v86` does not exist.

### Task 2: Implement Free Analyst Workbench

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add workbench data model**

Create `basicFreeAnalystWorkbench` from `basicSnapshot`, `basicFreeReport`, and existing freshness/profile/peer/K-line fields. It should return localized title, subtitle, boundary, decision cards, action labels, and free/premium comparison rows.

- [x] **Step 2: Render top workbench card**

Render `data-testid="basic-query-free-analyst-workbench-v86"` in quick mode immediately after `basic-query-next-actions-v85`, before the longer today brief. Include compact decision cards and action buttons for news, peers, K-line, and refresh.

- [x] **Step 3: Keep it no-AI**

All V86 buttons must reuse existing no-AI refresh/jump handlers. They must not call `analysisApi.analyzeAsync`.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v86-free-analyst-workbench.md`

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

Open `http://127.0.0.1:8018/?dsa_v86_smoke=1`, query `AAPL`, open quick analysis, confirm the V86 workbench appears above the longer report sections, and confirm its `看资讯`, `看同业`, and `看K线` buttons reach the target modules.

- [x] **Step 4: Commit cleanly**

Commit only V86 files and finish with a clean working tree.

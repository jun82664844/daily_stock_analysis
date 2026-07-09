# DSA V87 Free Visual Analyst Page Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Make the free quick-analysis page feel like a visual analyst dashboard that helps ordinary users understand trend, volume, support/resistance, and next steps before considering premium.

**Architecture:** Add one top-level V87 visual analyst section in `HomePage.tsx`, driven entirely by the existing no-AI quick snapshot, free report, trend points, indicators, and profile fields. The section should not add backend calls, AI calls, or paid-only gates; premium value is shown as data-source/model-depth upgrade, not as hidden UI.

**Tech Stack:** React, TypeScript, Vitest, Testing Library, existing SVG/Tailwind UI, existing DSA quick snapshot data.

---

### Task 1: Add Failing V87 Coverage

**Files:**
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [x] **Step 1: Write the failing test**

Add assertions in the existing no-AI quick-query test:
- `basic-query-visual-analyst-page-v87` exists
- shows `可视化研判页`
- shows `先看图，再读结论`
- shows `趋势轨道`
- shows `量价确认`
- shows `支撑压力`
- shows `经纪人下一步`
- shows `免费版可见`
- shows `高级版增强`
- clicking `看资讯` and `看K线` from the visual page does not call `analysisApi.analyzeAsync`

- [x] **Step 2: Run the test to verify it fails**

```powershell
npm run test -- --run src/pages/__tests__/HomePage.test.tsx
```

Expected: fail because `basic-query-visual-analyst-page-v87` does not exist.

### Task 2: Implement Visual Analyst Page

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`

- [x] **Step 1: Add visual data model**

Create `basicVisualAnalystPage` from `basicSnapshot` and `basicFreeReport`. It should include localized title/subtitle/boundary, sparkline points, support/resistance labels, volume bars, summary stats, next-step actions, and free-vs-premium copy.

- [x] **Step 2: Render V87 section**

Render `data-testid="basic-query-visual-analyst-page-v87"` in quick mode after the V86 workbench and before the long text report. Include:
- visual trend SVG
- support/resistance markers
- volume/price confirmation bars
- compact broker next-step cards
- no-AI boundary badge
- action buttons for news, peers, K-line, refresh

- [x] **Step 3: Keep it free and no-AI**

All actions must reuse existing refresh/jump handlers. They must not call `analysisApi.analyzeAsync`.

### Task 3: Verify And Commit

**Files:**
- Verify: `apps/dsa-web/src/pages/HomePage.tsx`
- Verify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Verify: `docs/superpowers/plans/2026-07-09-dsa-v87-free-visual-analyst-page.md`

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

Open `http://127.0.0.1:8018/?dsa_v87_smoke=1`, query `AAPL`, open quick analysis, confirm the V87 visual analyst page appears above the longer report sections, and confirm `看资讯`, `看同业`, and `看K线` buttons reach the target modules.

- [x] **Step 4: Commit cleanly**

Commit only V87 files and finish with a clean working tree.

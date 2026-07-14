# DSA V124 免费每日市场工作台 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 复用 V119/V121 的公开市场数据，在首页首屏增加三地市场时钟、跨市场今日时间线和最近查看入口，让游客无需登录、AI 或 API 额度也有每天返回的理由。

**Architecture:** 不新增第三方数据源和重复后端接口；组件只消费现有 `PublicMarketHomeResponse`，把各市场状态、指数和可追溯资讯整理成跨市场工作台。最近查看仅保存在浏览器本地，最多六条，不写平台账户数据；任一股票入口继续调用现有免费查询流程。

**Tech Stack:** React 19、TypeScript、Vitest、Testing Library、现有 FastAPI public market home、Python 发布门禁。

---

## 产品边界

- 游客可用，不要求登录，不调用 AI、BYOK、Ollama 或 Kronos。
- 只展示公开行情、市场状态、来源链接和浏览器本地最近查看。
- 不生成买卖指令、目标价、仓位、收益预测或投资建议。
- 没有可靠发布时间的资讯明确显示抓取时间，不伪装成刚发生。
- 任一市场不可用时只降级该市场，其他市场和最近查看仍可使用。
- 免费版与高级版保持同一信息架构；差异仅在数据源、刷新频率和 API 使用额度。

### Task 1: 最近查看本地模型

**Files:**
- Create: `apps/dsa-web/src/components/market-home/marketRecentV124.ts`
- Test: `apps/dsa-web/src/components/market-home/__tests__/marketRecentV124.test.ts`

- [x] **Step 1: 写失败测试**

断言首次为空、同一股票去重置顶、最多保留六条、损坏 JSON 返回空数组、存储内容不包含账户或 API Key 字段。

- [x] **Step 2: 运行 RED**

```powershell
cd E:\DSA项目-v124\apps\dsa-web
npm test -- --run src/components/market-home/__tests__/marketRecentV124.test.ts
```

预期：模块不存在或导出不存在，测试失败。

- [x] **Step 3: 实现最小模型**

导出 `readRecentMarketSymbols`、`rememberRecentMarketSymbol`、`clearRecentMarketSymbols` 和 `RECENT_MARKET_SYMBOLS_EVENT`；使用版本化 localStorage key，并把输入清洗成 `symbol/name/market/viewedAt`。

- [x] **Step 4: 运行 GREEN**

预期：最近查看模型测试全部通过。

### Task 2: 每日市场工作台组件

**Files:**
- Create: `apps/dsa-web/src/components/market-home/DailyMarketWorkbenchV124.tsx`
- Test: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx`

- [x] **Step 1: 写失败测试**

中文断言 A股/港股/美股市场状态、主要指数、跨市场时间线、来源与时间、最近查看和“仅提供资讯和数据”提示；英文断言完整英文；交互断言点击最近查看与榜单股票进入现有查询，清空最近查看只删除本地记录。

- [x] **Step 2: 运行 RED**

```powershell
npm test -- --run src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx
```

预期：组件不存在，测试失败。

- [x] **Step 3: 实现最小组件**

从 `PublicMarketHomeResponse` 派生三地市场状态、每个市场首个指数和最多六条跨市场资讯。资讯按 `publishedAt/observedAt/fetchedAt` 排序；链接使用新窗口和 `noopener noreferrer`；缺失数据展示明确不可用状态。

- [x] **Step 4: 运行 GREEN**

预期：组件双语、交互和降级测试全部通过。

### Task 3: 首页集成与点击留存

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

- [x] **Step 1: 写失败集成测试**

断言工作台位于动态榜单之前；点击榜单“查看股票”时先记录最近查看再调用 `onOpenSymbol`；点击数据详情和完整查询也更新同一条记录而不重复。

- [x] **Step 2: 运行 RED**

```powershell
npm test -- --run src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx
```

预期：找不到 V124 工作台或最近查看记录，测试失败。

- [x] **Step 3: 集成组件**

在现有市场焦点标题后渲染 `DailyMarketWorkbenchV124`；统一通过 `openSymbol` 包装器记录最近查看并调用原 `onOpenSymbol`，不修改价格提醒和按需详情的数据边界。

- [x] **Step 4: 运行目标回归**

```powershell
npm test -- --run src/components/market-home/__tests__/marketRecentV124.test.ts src/components/market-home/__tests__/DailyMarketWorkbenchV124.test.tsx src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx src/pages/__tests__/HomePage.test.tsx
npm run build
```

### Task 4: V124 门禁、文档和真实验收

**Files:**
- Create: `scripts/verify_platform_free_daily_market_workbench_v124.py`
- Create: `tests/test_platform_free_daily_market_workbench_v124_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: 写 verifier 失败测试并运行 RED**

门禁必须检查 V124 组件、最近查看模型、中文/英文、公开数据复用、无 AI 文案、资讯数据边界、测试和发布包可见性。

- [x] **Step 2: 实现 verifier 并运行 GREEN**

通过标记：

```text
DSA_PLATFORM_FREE_DAILY_MARKET_WORKBENCH_V124_OK guest=true public_data=true ai_used=false market_clocks=true cross_market_timeline=true recent_research=true bilingual=true investment_advice=false
```

- [x] **Step 3: 独立端口浏览器验收**

桌面和 390x844 移动视口检查三市场状态、跨市场时间线、来源链接、最近查看、点击查询、中文/英文、无横向溢出和无空白页。

- [x] **Step 4: Git 收口**

运行目标测试、生产构建、V124 verifier、release candidate verifier、敏感信息扫描、`git diff --check`；只提交 V124 文件，不 push，不修改用户数据。

## 完成定义

只有 TDD 红绿证据、目标回归、生产构建、V124 门禁、发布包门禁、桌面/移动浏览器验收、敏感扫描和独立 Git 提交全部成立，V124 才可标记完成。

# DSA V121 免费市场股票数据预览 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让游客和免费用户在动态首页按需展开股票数据详情，查看公开行情、区间、均线、近期表现、成交量、历史曲线和来源，而无需登录、AI 或 API 额度。

**Architecture:** 复用现有 `GET /api/v1/market-workspace/symbol/{symbol}` 公开接口，不新增第三方来源。首页只在用户点击“数据详情”后请求数据；独立详情组件负责字段清洗、缺失降级、客观数据描述和中英文展示。

**Tech Stack:** React 19、TypeScript、Recharts、Vitest、Testing Library、FastAPI 既有公开市场工作台、Python verifier。

---

## 产品边界

- 免登录可用，不扣减平台 API、BYOK、Ollama 或 Kronos 额度。
- 只显示公开行情与数学派生数据，不生成买卖指令、目标价、仓位或收益预测。
- 数据缺失显示“暂不可用”，不得伪装为零。
- 榜单首屏不预取详情，避免拖慢 V119 首页；每次只展开一个股票。
- 详情请求失败时保留榜单，并显示可重试的透明降级提示。
- V120 客服系统由其他任务负责，本计划不修改客服模块。

### Task 1: 详情组件测试先行

**Files:**
- Create: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx`
- Create: `apps/dsa-web/src/components/market-home/PublicMarketStockPreviewV121.tsx`

- [x] **Step 1: 写失败测试**

测试数据必须覆盖：

```ts
const detail = {
  symbol: 'AAPL',
  name: 'Apple Inc.',
  market: 'us',
  currency: 'USD',
  quote: { currentPrice: 317.31, open: 312, high: 319, low: 311, prevClose: 312.65, volume: 48_000_000, amount: 15_200_000_000, freshness: 'fresh', source: 'yahoo_chart_reference' },
  indicators: { ma5: 310, ma10: 305, ma20: 298, priceChange5d: 2.4, priceChange20d: 6.8, volumeChangeVsMa5: 12.5 },
  history: [{ date: '2026-07-10', close: 310 }, { date: '2026-07-11', close: 317.31 }],
  profile: { sector: 'Technology', industry: 'Consumer Electronics', marketCap: 4_700_000_000_000 },
  sources: [{ source: 'yahoo_chart_reference', status: 'fresh' }],
  warnings: [],
  headlines: [],
  aiUsed: false,
  informationalOnly: true,
};
```

断言中文指标、中英文切换、`未使用 AI`、来源、新鲜度、缺失字段降级和“仅提供资讯和数据”提示。

- [x] **Step 2: 运行测试并确认 RED**

```powershell
cd E:\DSA项目\apps\dsa-web
npm test -- --run src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx
```

预期：因组件不存在而失败。

- [x] **Step 3: 实现最小详情组件**

组件接口：

```ts
type Props = {
  language: 'zh' | 'en';
  item: MarketSecurityItem;
  detail: SymbolWorkspaceResponse | null;
  loading: boolean;
  error: string;
  onRetry: () => void;
  onClose: () => void;
  onOpenFull: (symbol: string) => void;
};
```

展示最新价、开高低昨收、MA5/MA10/MA20、5日和20日变化、量能相对 MA5、行业、市值、历史收盘曲线、来源状态和客观位置描述。

- [x] **Step 4: 运行测试并确认 GREEN**

预期：组件测试全部通过，无控制台错误。

### Task 2: 首页按需加载与交互

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`

- [x] **Step 1: 写失败集成测试**

断言：

- 每行有唯一“数据详情”图标按钮。
- 点击后调用 `marketWorkspaceApi.getSymbol(symbol)` 一次。
- 加载时显示进度，成功后显示详情面板。
- “进入完整查询”继续调用既有 `onOpenSymbol`。
- 请求失败显示降级提示并可重试。
- 切换市场或榜单时关闭旧详情。

- [x] **Step 2: 运行测试并确认 RED**

```powershell
cd E:\DSA项目\apps\dsa-web
npm test -- --run src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx
```

- [x] **Step 3: 实现按需加载**

父组件维护 `previewItem`、`previewDetail`、`previewLoading`、`previewError`；仅由按钮事件调用 `marketWorkspaceApi.getSymbol`，并在市场/榜单切换时清空状态。

- [x] **Step 4: 运行目标测试和 HomePage 回归**

```powershell
npm test -- --run src/components/market-home/__tests__/PublicMarketStockPreviewV121.test.tsx src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx src/pages/__tests__/HomePage.test.tsx
npm run build
```

### Task 3: V121 门禁与真实验收

**Files:**
- Create: `scripts/verify_platform_free_market_stock_preview_v121.py`
- Create: `tests/test_platform_free_market_stock_preview_v121_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] **Step 1: 新增 verifier 失败测试并确认 RED**

门禁必须检查组件、测试、按需请求、无 AI 文案、中英文、构建和发布包覆盖。

- [x] **Step 2: 实现 verifier 并确认 GREEN**

通过标记：

```text
DSA_PLATFORM_FREE_MARKET_STOCK_PREVIEW_V121_OK guest=true on_demand=true public_data=true ai_used=false bilingual=true mobile=true investment_advice=false
```

- [x] **Step 3: 重启 8018 并做浏览器验收**

桌面和 390x844 手机视口分别验收 A 股、港股、美股详情，确认首屏无预取、点击后加载、完整查询跳转、错误降级、无横向溢出。

- [x] **Step 4: Git 收口**

只暂存 V121 文件和共享文件中的 V121 片段，不暂存、回退或提交 V120 客服改动。独立干净工作树复跑完整 V121 verifier 后本地提交，不 push。

## 完成定义

只有 TDD 红绿证据、目标测试、构建、V121 verifier、发布包、实时接口、浏览器桌面/移动验收和独立 Git 提交全部成立，V121 才可标记完成。

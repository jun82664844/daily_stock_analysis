# DSA V142 个股研究总览与同业对比 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将个股快速分析页从连续堆叠面板重构为可扫描的研究总览与标签页，并为 A 股、美股、港股提供按需加载、来源可追溯的五年财务趋势和历史市盈率位置。

**Architecture:** 主查询继续复用现有 `BasicStockSnapshot`，不增加 AI、公共搜索或主链路网络请求。财务标签页首次打开时调用独立只读接口，使用 yfinance 公开财务报表和月线计算年度收入、净利润、每股收益及“年末价格/当年摊薄每股收益”历史样本；接口设缓存、超时和明确降级。前端用一个 V142 标签化组件整合总览、财务、同业、资讯事件、K 线和来源状态，旧版重复面板默认折叠但仍可展开。

**Tech Stack:** FastAPI、Pydantic、Python unittest、yfinance/pandas、React 18、TypeScript、Vitest、Testing Library、Tailwind CSS、Playwright。

---

### Task 1: 五年财务趋势与估值位置服务

**Files:**
- Create: `src/services/public_stock_research_overview_service.py`
- Modify: `api/v1/schemas/basic_query.py`
- Modify: `api/v1/endpoints/stocks.py`
- Test: `tests/test_public_stock_research_overview_v142.py`

- [ ] **Step 1: 写股票代码映射和财务趋势失败测试**

覆盖 `AAPL -> AAPL`、`0700.HK -> 0700.HK`、`600519.SH -> 600519.SS`、`000001.SZ -> 000001.SZ`，并用注入的假 `Ticker` 返回五个财年。

- [ ] **Step 2: 运行后端测试确认 RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_stock_research_overview_v142 -v`

Expected: FAIL，原因是 V142 服务和响应模型尚不存在。

- [ ] **Step 3: 实现最小服务**

实现：

```python
class PublicStockResearchOverviewService:
    def __init__(self, ticker_factory=None, *, cache_ttl_seconds=21600): ...
    def get_overview(self, stock_code: str) -> dict: ...

def to_public_research_symbol(stock_code: str) -> str | None: ...
```

返回字段包括 `status`、`source`、`updated_at`、`financial_years`、`valuation_position`、`warnings`、`ai_used=False` 和资讯边界。估值方法固定为 `fiscal_year_end_price_divided_by_diluted_eps`，不得包装成实时或预测估值。

- [ ] **Step 4: 增加匿名只读接口**

新增：

```python
@router.get("/{stock_code}/research-overview", response_model=PublicStockResearchOverviewResponse)
def get_public_stock_research_overview(stock_code: str): ...
```

加独立限流桶 `stock_research_overview`；加缓存；加超时/异常降级，不返回 provider 堆栈或密钥。

- [ ] **Step 5: 运行测试确认 GREEN**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_stock_research_overview_v142 -v`

Expected: PASS。

### Task 2: 标签化研究总览组件

**Files:**
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Create: `apps/dsa-web/src/components/research/StockResearchOverviewV142.tsx`
- Create: `apps/dsa-web/src/components/research/__tests__/StockResearchOverviewV142.test.tsx`

- [ ] **Step 1: 写组件失败测试**

覆盖：

```tsx
render(<StockResearchOverviewV142 snapshot={snapshot} language="zh" ... />);
expect(screen.getByRole('tab', { name: '财务趋势' })).toBeInTheDocument();
expect(stocksApi.researchOverview).not.toHaveBeenCalled();
await user.click(screen.getByRole('tab', { name: '财务趋势' }));
await waitFor(() => expect(stocksApi.researchOverview).toHaveBeenCalledWith('AAPL'));
```

并覆盖中文/英文切换、同业真实行情、资讯来源、K 线历史样本、数据缺失和接口错误降级。

- [ ] **Step 2: 运行前端测试确认 RED**

Run: `npm.cmd run test -- --run src/components/research/__tests__/StockResearchOverviewV142.test.tsx`

Workdir: `E:\DSA项目\apps\dsa-web`

Expected: FAIL，原因是组件和 API 方法尚不存在。

- [ ] **Step 3: 实现 API 类型和按需加载**

新增 `PublicStockResearchOverview` 类型和：

```ts
researchOverview(code: string): Promise<PublicStockResearchOverview>
```

组件首次进入“财务趋势”标签才请求接口，同一股票生命周期内不重复请求。

- [ ] **Step 4: 实现六个研究标签页**

标签：`研究总览`、`财务趋势`、`同业对比`、`资讯事件`、`K线样本`、`来源与边界`。所有标签均显示来源、新鲜度或不可用状态；不出现“买入、卖出、目标价、收益预测、仓位、止损、建议、策略、决策信号”等表达。

- [ ] **Step 5: 运行组件测试确认 GREEN**

Run: `npm.cmd run test -- --run src/components/research/__tests__/StockResearchOverviewV142.test.tsx`

Workdir: `E:\DSA项目\apps\dsa-web`

Expected: PASS。

### Task 3: 首页整合和重复内容收口

**Files:**
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/index.css`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: 写首页整合失败测试**

验证快速分析出现 `basic-query-research-overview-v142`，旧版重复研究面板默认处于折叠视觉状态，点击“展开全部详细模块”后恢复；游客仍可使用。

- [ ] **Step 2: 运行首页测试确认 RED**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx`

Workdir: `E:\DSA项目\apps\dsa-web`

- [ ] **Step 3: 接入 V142 并保留旧功能**

在快速分析首屏插入 V142。通过父级 `v142-condensed` 类隐藏重复的 V85-V103 介绍性面板，不删除资讯、A 股增强、Kronos、历史、自选或账户功能；用户可显式展开旧版全部详细模块。

- [ ] **Step 4: 复跑首页测试**

Run: `npm.cmd run test -- --run src/pages/__tests__/HomePage.test.tsx`

Expected: PASS。

### Task 4: 文档、门禁和发布包覆盖

**Files:**
- Create: `scripts/verify_platform_stock_research_overview_v142.py`
- Create: `tests/test_platform_stock_research_overview_v142_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] **Step 1: 写 verifier 失败测试**

门禁必须检查后端服务/接口、前端组件/标签、匿名无 AI 边界、禁用投资建议用语、按需加载、构建产物和发布包覆盖。

- [ ] **Step 2: 运行 verifier 测试确认 RED**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_stock_research_overview_v142_verifier -v`

- [ ] **Step 3: 实现 verifier 与文档更新**

成功标记固定为：

```text
DSA_PLATFORM_STOCK_RESEARCH_OVERVIEW_V142_OK
```

- [ ] **Step 4: 运行 verifier 确认 GREEN**

Run: `E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_stock_research_overview_v142.py`

Expected: 输出成功标记。

### Task 5: 完整验收与本地提交

- [ ] **Step 1: 后端回归**

运行 V142、基础查询、查询质量、平台限流和发布包相关 unittest。

- [ ] **Step 2: 前端回归与构建**

运行 V142 组件、HomePage、stocks API 测试及 `npm.cmd run build`。

- [ ] **Step 3: 真实浏览器验收**

在 `http://127.0.0.1:8018/?dsa_v142_smoke=1` 验收 AAPL、600519.SH、0700.HK：游客查询、快速分析、六标签切换、财务按需加载、同业/资讯/K线/来源状态、中英文、折叠/展开、无横向溢出。

- [ ] **Step 4: 安全和 Git 验收**

运行 `git diff --check`、发布包 verifier、敏感密钥扫描并确认无删除用户数据。

- [ ] **Step 5: 显式暂存并本地提交**

只暂存 V142 清单内文件，提交信息：

```text
feat: add stock research overview v142
```

提交后确认 `git status --short --untracked-files=all` 为空；不 push。

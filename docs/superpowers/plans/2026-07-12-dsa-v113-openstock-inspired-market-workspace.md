# DSA V113 OpenStock 启发式市场工作台 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在不复制 OpenStock AGPL 源码、不引入第二套账号和数据库的前提下，为 DSA 增加面向免费用户的市场总览、全局搜索、自选简报、资讯时间线、客观条件提醒和股票研究工作台，提高游客到注册用户、免费用户到高级会员的留存与转化。

**Architecture:** 新建独立 `/market` 市场工作台，复用 DSA 现有 FastAPI、SQLite、平台账号、自选、提醒、资讯、基础查询、K 线和多市场数据通道。后端只做有缓存、可降级的聚合 DTO，前端使用 React 19、Recharts 和现有设计系统，不引入 OpenStock 的 Next.js、MongoDB、Better Auth、Inngest、Finnhub 浏览器 Key 或 TradingView 嵌入组件。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy/SQLite、Pydantic、React 19、TypeScript、Zustand、Recharts、Vitest、Testing Library、Playwright。

---

## 1. 立项结论

OpenStock 适合作为产品体验参考，不作为代码依赖或运行时服务接入。V113 采用以下原则：

1. 不复制、修改、编译、分发或部署 `Open-Dev-Society/OpenStock` 的源码、组件、样式、图片和文字。
2. 不把 OpenStock 仓库放进 `external/`、Git submodule、npm dependency、Docker Compose 或生产镜像。
3. 不照搬 OpenStock 的 Next.js、MongoDB、Better Auth、Inngest 和邮件体系。
4. 只根据公开的通用产品能力独立设计 DSA 原生实现。
5. 新增文件头和文档中不写“基于 OpenStock 源码”；统一写“DSA 原生市场工作台”。
6. 任何 BOT 若发现需要复制上游实现才能继续，必须停止该步骤并改为基于 DSA 现有接口独立实现。

原因：OpenStock 使用 AGPL-3.0。直接把其代码合入并通过网站向用户提供服务，可能触发对应源代码提供义务，与 DSA 的商业运营和未来许可证选择产生冲突。本计划不是法律意见；上线前仍需由负责人完成许可证和数据授权审查。

## 2. 产品目标与免费版策略

### 2.1 用户主路径

```text
游客打开市场工作台
  -> 看到主要市场状态、涨跌分布和热门资讯
  -> 使用全局搜索打开股票工作台
  -> 查看行情、K 线、技术数据、公司资料、资讯和来源状态
  -> 注册后保存自选、条件提醒和每日简报偏好
  -> 免费 API 试用用于中性资讯摘要
  -> 额度不足时理解高级会员可增加平台 API 次数，也可使用自己的 API
```

### 2.2 免费版必须开放

- 游客无需登录查看 A 股、港股、美股市场总览的可用公开数据。
- 游客无需登录使用股票代码和公司名称搜索。
- 游客可查看基础行情、日线、均线、成交量、公司资料、资讯标题、来源和更新时间。
- 游客和免费用户可查看数据新鲜度、缓存状态、缺失字段和来源降级提示。
- 注册用户可保存个人自选、创建客观条件提醒、查看提醒历史和生成非 AI 每日简报。
- 免费用户继续使用现有平台 API 试用额度；V113 不建立第二套额度表。
- 免费额度用尽后，行情、K 线、公司资料、资讯标题、自选和提醒仍可使用。

### 2.3 高级会员差异

高级会员不靠隐藏基础数据制造付费压力。差异只来自现有或 V112 已定义的能力：

- 更高的平台 API 分析额度。
- 可使用自己的 OpenAI、Claude、DeepSeek API。
- 可使用批准的本地模型通道。
- 更高的自选数量、提醒数量、刷新频率和简报频率，由统一产品策略配置，不在前端硬编码。
- 可对同一份客观数据运行更长的 AI 中性摘要，但输出仍不得构成投资建议。

## 3. 永久合规边界

### 3.1 允许展示

- 行情、OHLC、成交量、成交额、换手率、涨跌幅、振幅和历史区间变化。
- MA5、MA10、MA20 等客观技术指标及计算方法。
- 公司资料、行业、板块、财务和估值字段。
- 新闻、公告、研报目录、资金流、龙虎榜和来源链接；没有真实来源时显示不可用。
- 市场涨跌分布、行业分布、数据完整度和数据新鲜度。
- 用户自定义条件及“条件已触发/未触发”的事实记录。
- AI 对已有数据的中性摘要，必须同时显示数据来源、更新时间和 AI 标记。

### 3.2 禁止展示

- 买入、卖出、加仓、减仓、持有、止损、止盈等交易指令。
- 推荐股票、首选标的、必涨、看多、看空、抄底、逃顶等引导性结论。
- 目标价、上涨空间、预期收益、收益概率和仓位建议。
- 根据用户持仓、资产、风险偏好生成个性化交易动作。
- 把热度、涨幅、数据完整度、资讯数量或 AI 文本表达成投资价值排名。

### 3.3 中立术语

| 禁止或高风险词 | V113 统一表达 |
| --- | --- |
| 热门推荐 | 浏览热度 / 数据关注度 |
| 强势股 | 涨幅靠前证券 |
| 弱势股 | 跌幅靠前证券 |
| 买入信号 | 用户设置的条件已触发 |
| 投资机会 | 市场数据变化 |
| 最佳股票 | 当前排序结果 |
| 风险评级 | 信息提示 / 数据异常提示 |
| 情绪看多/看空 | 资讯倾向字段；必须显示方法与来源 |

每个市场和股票页面底部固定显示：

```text
本页面只提供市场资讯、客观数据和用户自定义条件提醒，不提供投资建议、交易指令、目标价或收益预测。数据可能延迟或缺失，请以授权来源为准。
```

## 4. 数据与许可证边界

### 4.1 禁止直接接入

- 禁止在浏览器中放置 `NEXT_PUBLIC_FINNHUB_API_KEY` 或其他第三方密钥。
- 禁止抓取 OpenStock 自身页面和 API 作为数据源。
- 禁止复制 TradingView 嵌入代码或依赖其免费 Widget 作为核心 K 线。
- 禁止用单一第三方免费接口承诺 A 股、港股、美股全部实时。
- 禁止将第三方原始错误、Cookie、Token、Key、绝对路径和完整响应写入前端或审计日志。

### 4.2 复用 DSA 数据通道

- A 股：优先复用 V109/a-stock-data 适配器、现有基础行情和历史日线降级链。
- 港股：复用独立港股行情和公司资料通道，不经过 A 股适配器。
- 美股：复用现有美股行情、历史日线和 Yahoo chart 降级链。
- 资讯：复用 `api/v1/endpoints/intelligence.py` 和现有资讯池；公共搜索保持默认关闭或降级。
- K 线：复用 `FreeKlineResearchV101.tsx` 的标准化历史数据和 Recharts，不新增图表供应商。
- 自选：复用 `/api/v1/platform/watchlist`。
- 提醒：复用 `/api/v1/alerts` 和 V100 私有提醒边界。

### 4.3 数据状态

所有聚合项必须携带：

```python
class DataSourceState(BaseModel):
    source: str
    status: Literal["fresh", "cached", "stale", "unavailable"]
    observed_at: datetime | None
    fetched_at: datetime | None
    delay_seconds: int | None
    warning_code: str | None
```

`unavailable` 不能当作零参与排序，`stale` 不能显示为实时，缓存命中不能伪装成新拉取。

## 5. 当前基线和并发护栏

执行 V113 前必须运行：

```powershell
Set-Location E:\DSA项目
git status --short --branch --untracked-files=all
git diff --name-only
```

编写本文时，工作树正在进行 V112，至少涉及：

- `src/storage.py`
- `src/platform_accounts.py`
- `src/billing/*`
- `api/v1/endpoints/billing.py`
- `api/v1/schemas/billing.py`
- `src/services/api_boost_pack_service.py`
- `tests/test_platform_boost_pack_v112.py`
- V112 计划文档

V113 不得回退、覆盖、暂存或提交这些既有修改。若实现确实需要修改同一文件，先等待 V112 提交形成干净基线；不得使用 `git stash`、`git reset --hard`、`git checkout --`、`git clean -fd` 或 `git add -A` 规避冲突。

## 6. API 契约

### 6.1 市场总览

```http
GET /api/v1/market-workspace/overview?market=cn
```

```json
{
  "market": "cn",
  "as_of": "2026-07-12T10:00:00Z",
  "session_state": "closed",
  "indices": [],
  "breadth": {"advancers": 0, "decliners": 0, "unchanged": 0, "unavailable": true},
  "movers": [],
  "heatmap": [],
  "headlines": [],
  "sources": [],
  "warnings": ["market_breadth_unavailable"],
  "cache": {"hit": false, "age_seconds": 0, "ttl_seconds": 60},
  "informational_only": true
}
```

`market` 只接受 `cn`、`hk`、`us`。加密货币继续走现有查询入口，不在 V113 市场热力图中冒充证券市场。

### 6.2 全局搜索

```http
GET /api/v1/market-workspace/search?q=AAPL&markets=cn,hk,us&limit=8
```

每项返回：`symbol`、`name`、`market`、`exchange`、`currency`、`match_type`、`source_state`。服务端最少输入 1 个非空字符，最多 64 字符，最多返回 20 项；不得返回任意 HTML。

### 6.3 股票工作台

```http
GET /api/v1/market-workspace/symbol/AAPL
```

返回：

- 标准化行情和更新时间。
- 最多 120 根日线 OHLCV。
- MA5/MA10/MA20 和区间变化。
- 公司资料、财务和估值的可用字段。
- 最近资讯和公告目录；正文按授权边界决定。
- 用户未登录时 `personalization=null`。
- 登录时只返回当前用户自选状态和提醒数量，不返回其他用户数据。
- 每个模块独立 `source_state`，单模块失败不得让整页 500。

### 6.4 个人市场简报

```http
GET /api/v1/market-workspace/daily-brief
```

必须登录。默认不使用 AI，只汇总当前用户自选中最多 20 只证券的价格变化、资讯新增、公告新增、数据异常和提醒触发。没有自选时返回空简报和添加自选入口，不自动加入股票。

## 7. 文件职责图

### 7.1 新建后端文件

- `api/v1/schemas/market_workspace.py`：V113 公开 DTO，只包含标准化和脱敏字段。
- `api/v1/endpoints/market_workspace.py`：overview、search、symbol、daily-brief 路由。
- `src/services/market_workspace_service.py`：多市场聚合、缓存、降级和来源状态。
- `src/services/market_search_service.py`：代码/名称搜索、市场识别和去重。
- `src/services/market_daily_brief_service.py`：当前用户非 AI 自选简报。
- `tests/test_market_workspace_v113.py`：聚合、缓存、市场隔离和降级测试。
- `tests/test_market_search_v113.py`：搜索规范化、去重、限流和注入测试。
- `tests/test_market_daily_brief_v113.py`：用户隔离、空自选和非 AI 测试。
- `scripts/verify_platform_market_workspace_v113.py`：总验收器。
- `tests/test_platform_market_workspace_v113_verifier.py`：验收器和发布包可见性测试。

### 7.2 新建前端文件

- `apps/dsa-web/src/api/marketWorkspace.ts`：V113 API 客户端和 camelCase 映射。
- `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`：独立 `/market` 页面，只负责布局与状态组合。
- `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`。
- `apps/dsa-web/src/components/market-workspace/GlobalStockCommandV113.tsx`：全局快捷搜索。
- `apps/dsa-web/src/components/market-workspace/MarketPulseV113.tsx`：指数、市场状态和数据时间。
- `apps/dsa-web/src/components/market-workspace/MarketHeatmapV113.tsx`：证券涨跌网格；行业缺失时不伪造行业分组。
- `apps/dsa-web/src/components/market-workspace/MarketMoversV113.tsx`：透明排序的涨跌和成交活跃列表。
- `apps/dsa-web/src/components/market-workspace/MarketNewsTimelineV113.tsx`：资讯时间线和来源状态。
- `apps/dsa-web/src/components/market-workspace/WatchlistBriefV113.tsx`：登录用户自选简报。
- `apps/dsa-web/src/components/market-workspace/SymbolWorkspaceV113.tsx`：股票行情、K 线、资料、资讯和提醒入口。
- `apps/dsa-web/src/components/market-workspace/__tests__/*.test.tsx`：组件单测。
- `apps/dsa-web/e2e/market-workspace-v113.spec.ts`：中英文、多市场、多角色浏览器验收。

### 7.3 修改文件

- `api/v1/endpoints/__init__.py`：导出 V113 endpoint。
- `api/v1/router.py`：挂载 `/market-workspace`。
- `apps/dsa-web/src/App.tsx`：增加 `/market` 路由。
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`：增加“市场”导航。
- `apps/dsa-web/src/i18n/uiText.ts`：中英文页面文案。
- `.env.example`：V113 开关、缓存和匿名限流配置。
- `scripts/verify_platform_release_candidate_package.py`：要求 V113 文件可见并分类。
- `tests/test_platform_release_candidate_package.py`：missing-file 失败路径。
- `docs/superpowers/platform-product-rules.md`：记录免费市场工作台和合规边界。
- `docs/superpowers/platform-local-v1-acceptance-status.md`：记录本地验收状态。
- `docs/superpowers/platform-release-candidate-manifest.md`：登记新增文件。
- `docs/superpowers/platform-review-slices.md`：新增 V113 review slice。
- `docs/CHANGELOG.md`：在 `[Unreleased]` 扁平增加 V113 条目。

### 7.4 明确不修改

- 不修改 V112 计费、加油包和模型连接器语义。
- 不修改平台账号表、自选表和提醒表结构。
- 不修改现有首页长页面的分析结果结构；市场工作台使用独立路由。
- 不新增 MongoDB、Redis、Inngest、Better Auth 或第二套邮件服务。
- 不新增真实支付、真实生产密钥、域名、HTTPS/WAF 或生产部署。

## 8. 实施任务

### Task 1: 建立许可证护栏、功能开关和公开 DTO

**Files:**
- Create: `api/v1/schemas/market_workspace.py`
- Modify: `.env.example`
- Test: `tests/test_market_workspace_v113.py`

- [ ] **Step 1: 写失败测试固定开关关闭和 DTO 脱敏**

```python
def test_market_workspace_is_disabled_by_default(client):
    response = client.get("/api/v1/market-workspace/overview?market=us")
    assert response.status_code == 404


def test_overview_schema_does_not_expose_raw_provider_payload():
    fields = MarketWorkspaceOverview.model_fields
    assert "raw" not in fields
    assert "api_key" not in fields
    assert "provider_response" not in fields
```

- [ ] **Step 2: 运行 RED**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_market_workspace_v113 -v
```

Expected: FAIL，V113 schema 或 route 尚不存在。

- [ ] **Step 3: 增加安全默认配置**

```dotenv
PLATFORM_MARKET_WORKSPACE_V113_ENABLED=false
PLATFORM_MARKET_WORKSPACE_CACHE_TTL_SECONDS=60
PLATFORM_MARKET_WORKSPACE_STALE_TTL_SECONDS=900
PLATFORM_MARKET_WORKSPACE_ANON_RATE_LIMIT_PER_MINUTE=20
PLATFORM_MARKET_WORKSPACE_MAX_SEARCH_RESULTS=20
```

- [ ] **Step 4: 实现 DTO**

DTO 使用 `extra="forbid"`，时间统一 ISO 8601，金额同时返回 `currency`，缺失数字使用 `null` 而不是 `0`。任何 `warning_code` 使用稳定枚举，不包含原始异常文本。

- [ ] **Step 5: 运行 GREEN**

运行 Task 1 测试并确认全部通过。

### Task 2: 实现有缓存、可降级的多市场总览

**Files:**
- Create: `src/services/market_workspace_service.py`
- Create: `api/v1/endpoints/market_workspace.py`
- Modify: `api/v1/endpoints/__init__.py`
- Modify: `api/v1/router.py`
- Test: `tests/test_market_workspace_v113.py`

- [ ] **Step 1: 写失败测试固定市场隔离和局部降级**

```python
def test_cn_overview_never_calls_us_or_hk_provider(service, providers):
    service.get_overview("cn")
    providers.cn.assert_called_once()
    providers.us.assert_not_called()
    providers.hk.assert_not_called()


def test_news_failure_keeps_quote_and_heatmap(service):
    overview = service.get_overview("us")
    assert overview.indices
    assert overview.heatmap
    assert "market_news_unavailable" in overview.warnings
```

- [ ] **Step 2: 写失败测试固定缓存和过期语义**

```python
def test_fresh_cache_avoids_duplicate_network_calls(service, provider):
    first = service.get_overview("us")
    second = service.get_overview("us")
    assert provider.call_count == 1
    assert first.cache.hit is False
    assert second.cache.hit is True
```

- [ ] **Step 3: 运行 RED**

运行 `tests.test_market_workspace_v113`，确认 service 不存在导致失败。

- [ ] **Step 4: 实现聚合顺序**

```text
识别 market
  -> 读取 60 秒内缓存
  -> 只调用对应市场指数/行情通道
  -> 计算涨跌分布和透明排序
  -> 读取资讯池，不启动公共搜索
  -> 标准化 source_state
  -> 写入缓存
  -> 单模块失败时保留其他模块
```

热力图只使用本次快照已有数据，不为补行业字段额外逐股请求。网格按 `change_pct` 颜色映射，面积按可用的 `market_cap` 或 `turnover`；两者都缺失时等面积并显示“规模字段不可用”。

- [ ] **Step 5: 增加匿名限流**

限流键使用散列后的客户端网络标识和 route，不保存完整 IP。429 返回 `rate_limited`、`retry_after_seconds`，前端保留旧缓存。

- [ ] **Step 6: 运行回归**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_market_workspace_v113 tests.test_platform_query_quality_v4 -v
```

Expected: PASS；A/H/美股既有查询不回归。

### Task 3: 实现全局股票搜索

**Files:**
- Create: `src/services/market_search_service.py`
- Modify: `api/v1/endpoints/market_workspace.py`
- Test: `tests/test_market_search_v113.py`

- [ ] **Step 1: 写搜索规范化和安全失败测试**

```python
def test_search_normalizes_three_markets(service):
    assert service.search("贵州茅台", ["cn"], 8)[0].symbol == "600519.SH"
    assert service.search("腾讯", ["hk"], 8)[0].symbol == "0700.HK"
    assert service.search("Apple", ["us"], 8)[0].symbol == "AAPL"


def test_search_rejects_html_and_caps_results(client):
    response = client.get("/api/v1/market-workspace/search", params={"q": "<script>", "limit": 1000})
    assert response.status_code == 400
```

- [ ] **Step 2: 运行 RED**

运行搜索测试，确认 service 不存在。

- [ ] **Step 3: 实现搜索优先级**

精确代码 > 代码前缀 > 名称前缀 > 名称包含。按市场和规范化代码去重；不以涨幅、热度或模型判断排序。远程搜索超时不超过 2 秒，失败时返回本地符号索引结果。

- [ ] **Step 4: 运行 GREEN**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_market_search_v113 -v
```

### Task 4: 建立独立市场工作台页面

**Files:**
- Create: `apps/dsa-web/src/api/marketWorkspace.ts`
- Create: `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/MarketPulseV113.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/MarketHeatmapV113.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/MarketMoversV113.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/MarketNewsTimelineV113.tsx`
- Modify: `apps/dsa-web/src/App.tsx`
- Modify: `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- Test: `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`

- [ ] **Step 1: 写失败测试固定第一屏信息层级**

```tsx
it('shows market state, as-of time, breadth and source status before movers', async () => {
  render(<MarketWorkspacePage />);
  expect(await screen.findByText('市场状态')).toBeInTheDocument();
  expect(screen.getByText('数据时间')).toBeInTheDocument();
  expect(screen.getByText('涨跌分布')).toBeInTheDocument();
  expect(screen.getByText('数据来源')).toBeInTheDocument();
});
```

- [ ] **Step 2: 写失败测试固定 A/H/美股切换**

切换市场后只请求选中市场；前一市场的旧数据不能短暂显示为新市场。请求失败保留本市场上一次缓存并显示降级状态。

- [ ] **Step 3: 运行 RED**

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/pages/__tests__/MarketWorkspacePage.test.tsx
```

- [ ] **Step 4: 实现工作台布局**

桌面端顺序：市场切换和时间 -> 指数/涨跌分布 -> 热力网格 -> 涨跌与活跃列表 -> 资讯时间线。移动端改为单列，禁止页面横向滚动。页面段落使用全宽布局，不把整页堆成嵌套卡片。

- [ ] **Step 5: 运行 GREEN 和 build**

```powershell
npm test -- src/pages/__tests__/MarketWorkspacePage.test.tsx src/components/market-workspace
npm run lint
npm run build
```

### Task 5: 增加 Ctrl/Cmd + K 全局搜索

**Files:**
- Create: `apps/dsa-web/src/components/market-workspace/GlobalStockCommandV113.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/__tests__/GlobalStockCommandV113.test.tsx`
- Modify: `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`

- [ ] **Step 1: 写失败测试**

覆盖快捷键打开、输入防抖、键盘上下选择、Enter 打开、Escape 关闭、无结果、网络降级和中文/英文可访问名称。

- [ ] **Step 2: 运行 RED**

运行组件测试，确认组件不存在。

- [ ] **Step 3: 实现**

输入 180ms 防抖；少于 1 个字符不请求；缓存最近 10 次搜索仅保存代码、名称和市场，不保存用户输入全文。选择结果打开 `/market?symbol=AAPL`，不自动运行 AI。

- [ ] **Step 4: 运行 GREEN**

运行组件、页面和 API 客户端测试。

### Task 6: 复用自选和提醒形成留存闭环

**Files:**
- Create: `src/services/market_daily_brief_service.py`
- Create: `tests/test_market_daily_brief_v113.py`
- Create: `apps/dsa-web/src/components/market-workspace/WatchlistBriefV113.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/__tests__/WatchlistBriefV113.test.tsx`
- Modify: `api/v1/endpoints/market_workspace.py`
- Modify: `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`

- [ ] **Step 1: 写用户隔离失败测试**

```python
def test_daily_brief_contains_only_current_users_watchlist(client_a, client_b):
    add_watchlist(client_a, "AAPL")
    add_watchlist(client_b, "600519.SH")
    body = client_a.get("/api/v1/market-workspace/daily-brief").json()
    assert [item["symbol"] for item in body["items"]] == ["AAPL"]
```

- [ ] **Step 2: 写非 AI 和空状态测试**

简报生成不得调用 LLM；空自选返回 200、`items=[]` 和“添加自选”操作，不生成推荐证券。

- [ ] **Step 3: 运行 RED 后实现**

读取当前用户最多 20 只自选，批量复用缓存行情、资讯新增计数和提醒触发记录。单只失败只给该项 warning。

- [ ] **Step 4: 前端接入**

游客显示“登录后保存自选和条件提醒”，但市场查询继续可用。注册用户可从股票工作台加入/移除自选、创建客观提醒、查看最近触发，不显示买卖措辞。

- [ ] **Step 5: 运行后端和前端测试**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_market_daily_brief_v113 tests.test_platform_user_journey -v
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/market-workspace/__tests__/WatchlistBriefV113.test.tsx src/pages/__tests__/MarketWorkspacePage.test.tsx
```

### Task 7: 建立股票研究工作台

**Files:**
- Create: `apps/dsa-web/src/components/market-workspace/SymbolWorkspaceV113.tsx`
- Create: `apps/dsa-web/src/components/market-workspace/__tests__/SymbolWorkspaceV113.test.tsx`
- Modify: `src/services/market_workspace_service.py`
- Modify: `api/v1/endpoints/market_workspace.py`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`
- Test: `tests/test_market_workspace_v113.py`

- [ ] **Step 1: 写模块独立降级测试**

行情可用但资讯失败时仍显示行情和 K 线；历史日线失败时仍显示最新行情和公司资料；资料失败时不能让价格消失。

- [ ] **Step 2: 写免费边界测试**

游客打开 `AAPL`、`600519.SH`、`0700.HK` 时不得触发 LLM 或扣 AI 额度。页面必须展示来源、更新时间和“未使用 AI”。

- [ ] **Step 3: 运行 RED 后实现后端聚合**

复用现有基础查询 DTO，返回最多 120 根日线。技术指标由已有历史数据本地计算，不为每个指标再次请求网络。

- [ ] **Step 4: 实现前端阅读顺序**

```text
证券名称、代码、市场、币种、数据时间
  -> 最新行情和数据新鲜度
  -> K 线与成交量
  -> 客观技术指标
  -> 公司资料与财务字段
  -> 资讯/公告时间线
  -> 自选和条件提醒
  -> 可选 AI 中性摘要入口
```

AI 按钮使用 V112 模型选择和额度，不在 V113 新建模型设置。AI 失败不能清空免费数据。

- [ ] **Step 5: 运行三市场测试**

运行后端 V113 测试和前端 `SymbolWorkspaceV113` 测试，覆盖 A/H/美股、缺失值、过期缓存和中英文。

### Task 8: 完成中英文、移动端、无障碍和安全门禁

**Files:**
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Modify: all V113 frontend components
- Test: all V113 frontend tests
- Test: `apps/dsa-web/e2e/market-workspace-v113.spec.ts`

- [ ] **Step 1: 中英文完整性**

中文模式不出现 `Market breadth`、`Top movers`、`Watchlist brief`、`stale` 等未翻译状态；英文模式不出现中文业务文案。证券代码、公司法定名称和来源品牌不强制翻译。

- [ ] **Step 2: 无障碍**

键盘可操作市场切换、搜索、列表和提醒按钮；热力图颜色之外必须同时显示涨跌数值；所有图表提供文字摘要；焦点不困在搜索弹层。

- [ ] **Step 3: 响应式**

验证 390x844、768x1024、1440x900。禁止按钮文字溢出、热力图遮挡、页面横向滚动和固定高度截断。

- [ ] **Step 4: 安全**

搜索结果和资讯标题作为文本渲染，不使用未净化 `dangerouslySetInnerHTML`。外部来源链接使用 `noopener noreferrer`。错误信息经过稳定错误码映射。

- [ ] **Step 5: 前端总回归**

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/market-workspace src/pages/__tests__/MarketWorkspacePage.test.tsx src/api
npm run lint
npm run build
```

### Task 9: 验收器、发布包、浏览器验收和 Git 收口

**Files:**
- Create: `scripts/verify_platform_market_workspace_v113.py`
- Create: `tests/test_platform_market_workspace_v113_verifier.py`
- Modify: release docs and verifier files listed in section 7.3

- [ ] **Step 1: 实现 V113 验收器**

验收器必须运行：

- V113 后端三组测试。
- 既有 query quality、用户隔离、提醒和 release package 测试。
- V113 前端组件/API/页面测试。
- `npm run lint` 和 `npm run build`。
- AGPL 隔离扫描：仓库不得新增 OpenStock 源文件、图片、版权头、npm/git 依赖和 Docker 服务。
- 密钥扫描：不得出现真实 Key、Cookie、Token、Mongo URI 或 Finnhub 浏览器 Key。

全部通过后打印：

```text
DSA_PLATFORM_MARKET_WORKSPACE_V113_OK markets=cn,hk,us guest=true watchlist=true alerts=true ai_required=false agpl_code_copied=false
```

- [ ] **Step 2: 真实浏览器验收**

在 `http://127.0.0.1:8018/market?dsa_v113_smoke=1` 验证：

1. 游客中文：A 股总览、搜索贵州茅台、打开股票工作台，不登录、不扣 AI。
2. 游客英文：美股总览、搜索 AAPL、全页面英文。
3. 免费注册用户：港股总览、搜索 0700.HK、加入自选、创建客观条件提醒、刷新后仍存在。
4. 用户 A/B 隔离：互相看不到自选、简报和提醒。
5. 数据源失败：页面保留缓存并准确显示 stale/unavailable。
6. 390x844 和 1440x900：无空白页、无横向溢出、无遮挡。
7. 浏览器 console 无未处理异常，network 不出现真实密钥。

- [ ] **Step 3: 同步长期文档**

更新产品规则、验收状态、manifest、review slices 和 changelog；明确“参考产品能力，未复制 OpenStock AGPL 源码”。

- [ ] **Step 4: Git 护栏**

```powershell
git diff --check
git diff --cached --check
git status --short --untracked-files=all
```

不得暂存 V112 或用户其他窗口留下的文件。只在潘总明确授权提交后，使用逐文件 `git add`；禁止 `git add -A`。不得 push。

## 9. 完成判定

V113 只有同时满足以下条件才可宣布完成：

1. `/market` 为独立、可用、非空白的市场工作台。
2. 游客无需登录、无需 AI 即可查看 A/H/美股可用市场数据并搜索股票。
3. 市场总览、搜索、股票工作台、自选简报和提醒形成完整闭环。
4. 免费额度用尽后，免费数据功能仍然可用。
5. 所有数据项带来源、时间、新鲜度和降级状态。
6. 任一数据模块失败不拖垮整个页面。
7. 中文模式完整中文，英文模式完整英文。
8. 页面只提供资讯、数据和用户条件提醒，不产生投资建议。
9. 未复制或依赖 OpenStock AGPL 源码、资产和运行服务。
10. 未新增 MongoDB、第二套账号、浏览器密钥和 TradingView 核心依赖。
11. V113 verifier、release package、后端测试、前端测试、lint、build 和浏览器验收全部通过。
12. 当前 V112 和用户既有改动没有被覆盖、删除、误暂存或误提交。

## 10. 回滚方案

1. 设置 `PLATFORM_MARKET_WORKSPACE_V113_ENABLED=false`，后端返回 404，旧查询、自选、提醒和分析入口保持不变。
2. 前端隐藏“市场”导航和 `/market` 路由，不删除用户自选和提醒。
3. V113 只读缓存可以删除重建，但不得删除行情历史、分析历史、用户、自选或提醒数据。
4. 若单个市场通道不稳定，只关闭该市场聚合，不关闭其他市场。

## 11. BOT 连续目标指令

将下面整段交给负责 DSA 的 BOT：

```text
/goal 按 E:\DSA项目\docs\superpowers\plans\2026-07-12-dsa-v113-openstock-inspired-market-workspace.md 完整执行 DSA V113。

结果目标：在 DSA 原生架构内完成 /market 市场工作台，包括 A股/港股/美股市场总览、全局股票搜索、股票研究工作台、自选简报、资讯时间线和客观条件提醒。免费游客不登录、不使用 AI 也能获得有用数据；高级会员差异继续复用平台 API、BYOK 和本地模型额度。

硬约束：
1. 不复制、修改、安装、部署或依赖 OpenStock AGPL 源码、组件、资产、Docker 服务和 npm 包。
2. 不新增 Next.js、MongoDB、Better Auth、Inngest、TradingView 核心依赖或浏览器侧第三方密钥。
3. 只提供资讯、客观数据和用户自定义条件提醒；禁止投资建议、交易指令、目标价和收益预测。
4. 先检查并保护当前 V112 脏树，不回退、不覆盖、不清理、不暂存、不提交其他窗口的改动。
5. 按 TDD 逐 Task 执行，先看测试按预期失败，再写最小实现，再跑回归。
6. 普通测试失败、代码错误、依赖问题、8018 旧进程和前端缓存要自行诊断并继续，不要中途让潘总逐步确认。
7. 不接真实支付、真实生产 Key、生产部署、域名、HTTPS/WAF 或法律定稿。
8. 未经潘总明确授权，不执行 git commit、git push；禁止 git add -A、git reset --hard、git checkout --、git clean -fd。

验收要求：
- 完成计划 Task 1-9。
- V113 verifier 输出 DSA_PLATFORM_MARKET_WORKSPACE_V113_OK。
- 后端相关测试、前端相关测试、lint、build、release package、敏感信息扫描和 git diff --check 全部通过。
- 重启 8018 后完成中英文、游客/免费用户/A-B隔离、A股/港股/美股、桌面/移动真实浏览器验收。
- 明确记录每个第三方数据源的 fresh/cached/stale/unavailable 状态，不把降级伪装成实时成功。
- 最终报告修改文件、测试数量、浏览器证据、未验收边界和完整 git status；只有全部本地门禁通过才结束目标。
```

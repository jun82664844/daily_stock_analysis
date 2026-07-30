# DSA V136 市场事件复盘与实际行情反应实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V135 真实市场日历之后，为已经发生的 A股、港股、美股事件补充可核查的价格、成交量和市场基准同期数据，让免费用户无需登录、API Key 或 AI 即可进行事件复盘。

**Architecture:** 新增独立的 `PublicMarketEventReactionService`，从已经缓存的公共首页事件中选择最近发生、来源明确的最多 6 个事件，并行读取 Yahoo Chart 无密钥日线数据。由于公开日历只有事件日期、没有精确发布时间，服务以事件日收盘作为保守基线，下一交易日才计为 1 日，计算后续 1/3/5/20 个交易日的客观变化、同期市场基准变化和事件日前 5 日量能比；新公开端点独立限流、缓存和超时，前端延迟加载，不阻塞公共首页。所有字段都使用“观察”“同期”“相对变化”等中性表述，不推断事件导致行情变化。

**Tech Stack:** Python 3.12、requests、FastAPI/Pydantic、React 19、TypeScript、Vitest、Testing Library、Vite、Playwright、8018 真实浏览器验收。

**Product boundary:** 仅提供公开事件和实际市场数据；不生成因果结论、影响评级、目标价、收益预测、买卖建议、仓位建议或交易指令。事件与行情同期展示不代表因果关系。公开端点不调用 AI、不读取平台或用户 API Key、不写数据库、不发送通知、不上传本地关注状态。

---

### Task 1: 事件行情反应计算服务

**Files:**
- Create: `src/services/public_market_event_reaction_service.py`
- Create: `tests/test_public_market_event_reaction_service_v136.py`

- [x] **Step 1: 写失败测试**

覆盖以下行为：

```python
service = PublicMarketEventReactionService(
    event_loader=lambda: {"events": events},
    history_loader=fake_history,
    clock=lambda: "2026-07-30T00:00:00+00:00",
)
payload = service.build()
assert payload["ai_used"] is False
assert payload["informational_only"] is True
assert payload["items"][0]["windows"][0]["trading_days"] == 1
assert payload["items"][0]["windows"][0]["symbol_return_percent"] == 2.0
assert payload["items"][0]["windows"][0]["benchmark_return_percent"] == 1.0
assert payload["items"][0]["windows"][0]["relative_return_percent"] == 1.0
```

同时验证：
- 只处理 `time_kind=scheduled`、`classification_source=provider_schedule` 且已经发生的事件。
- 公司事件必须有合法 A股、港股或美股代码；FOMC 宏观事件使用标普500指数作为观察对象。
- A股 `.SH` 转为 Yahoo `.SS`，`.SZ`、港股和美股使用安全规范化代码。
- 基线是事件所在市场的事件日收盘；公开日历只有日期、没有精确发布时间，因此不把事件日前收盘到事件日收盘的波动归入“事件后”窗口，下一交易日才计为 1 日。
- 观察窗口按对应市场基准指数的交易日推进；个股停牌或缺少目标市场交易日行情时显示 `insufficient_data`，不得跳到更晚交易日。
- 周末和节假日后的窗口成熟度按市场已有交易日判断，不按 UTC 自然日近似。
- 同期基准分别为 `000001.SS`、`^HSI`、`^GSPC`。
- 量能比为观察窗口平均成交量相对事件前 5 个交易日平均成交量。
- 数据不足显示 `pending` 或 `insufficient_data`，不得补造数值。
- 去重行情代码、并发读取、总等待有界；单来源失败不影响其他事件。
- 每次最多 6 个事件；响应、单代码缓存和陈旧缓存都有容量与时间上限。
- 45 日历史事件窗口跨报告期或年份时，补取上一巨潮报告期和上一年度 FOMC 日程；单来源缓存最多保留 72 条事件。
- URL 仅允许 HTTPS Yahoo Chart；响应体有大小上限。
- 源码不得包含 AI、API Key、数据库写入、通知、因果评级或交易建议路径。

- [x] **Step 2: 运行测试确认失败**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_reaction_service_v136
```

预期：因模块尚不存在而失败。

- [x] **Step 3: 实现最小服务**

核心接口：

```python
class PublicMarketEventReactionService:
    def build(self) -> dict[str, Any]:
        ...
```

默认配置：

```text
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_MAX_EVENTS=6
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_TIMEOUT_SECONDS=4
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_CACHE_TTL_SECONDS=900
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_STALE_TTL_SECONDS=21600
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_HISTORY_CACHE_MAX_ENTRIES=32
PLATFORM_PUBLIC_MARKET_CALENDAR_CACHE_MAX_ENTRIES=64
PLATFORM_RATE_LIMIT_MAX_BUCKETS=4096
```

- [x] **Step 4: 运行测试确认通过**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_reaction_service_v136
```

### Task 2: 公开 API 契约与限流端点

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `api/v1/endpoints/market_workspace.py`
- Create: `tests/test_public_market_event_reaction_api_v136.py`

- [x] **Step 1: 写失败测试**

验证：
- `GET /api/v1/market-workspace/event-reactions` 游客可访问。
- 平台市场工作台、公共首页和 V136 开关都必须开启。
- 使用 `market_workspace_event_reactions` 独立限流桶。
- 响应严格校验事件、基线、观察窗口、基准、来源、缓存和安全字段。
- 开关关闭返回 404；服务异常返回 503 且不泄漏内部错误。

- [x] **Step 2: 运行测试确认失败**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_reaction_api_v136
```

- [x] **Step 3: 实现契约与端点**

新增 DTO：

```python
class MarketEventReactionWindow(StrictModel):
    trading_days: Literal[1, 3, 5, 20]
    status: Literal["available", "pending", "insufficient_data"]
    observed_date: Optional[str] = None
    symbol_return_percent: Optional[float] = None
    benchmark_return_percent: Optional[float] = None
    relative_return_percent: Optional[float] = None
    volume_ratio: Optional[float] = None

class PublicMarketEventReactionResponse(StrictModel):
    as_of: str
    items: List[PublicMarketEventReaction] = Field(default_factory=list, max_length=6)
    warnings: List[str] = Field(default_factory=list)
    cache: MarketCacheState
    ai_used: bool = False
    informational_only: bool = True
```

- [x] **Step 4: 运行 API 与服务回归**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_event_reaction_service_v136 tests.test_public_market_event_reaction_api_v136 tests.test_public_market_home_v116
```

### Task 3: 前端 API 与双语事件复盘面板

**Files:**
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/api/__tests__/marketWorkspace.test.ts`
- Create: `apps/dsa-web/src/components/market-home/MarketEventReactionPanelV136.tsx`
- Create: `apps/dsa-web/src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx`

- [x] **Step 1: 写失败测试**

验证：
- 默认显示 1 个交易日观察窗口，可切换 3/5/20 日。
- 显示事件标题、计划日期、观察对象、基准、实际涨跌、同期基准、相对变化、量能比、数据日期和来源状态。
- 正负数使用涨跌颜色但不出现“利好、利空、买入、卖出、机会、风险评级”等判断。
- `pending`、`insufficient_data`、空列表、429、503、陈旧缓存都有中英文诚实状态。
- 中文模式不混入普通英文动态文案，英文模式不混入普通中文动态文案。
- 显示“同期表现不代表因果关系”和“不构成投资建议”。
- 查询按钮继续进入已有个股免费查询。
- 390px 移动端不横向溢出。

- [x] **Step 2: 运行测试确认失败**

```powershell
cd E:\DSA项目\apps\dsa-web
npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx
```

- [x] **Step 3: 实现 API 规范化与面板**

前端调用：

```typescript
async getEventReactions(): Promise<PublicMarketEventReactionResponse> {
  const response = await apiClient.get('/api/v1/market-workspace/event-reactions');
  return normalizeEventReactionResponse(toCamelCase(response.data));
}
```

面板使用分段按钮切换 1/3/5/20 日观察窗口；加载失败只影响本面板，不影响 V135 日历和首页其他内容。

- [x] **Step 4: 运行聚焦测试确认通过**

```powershell
npm.cmd run test -- --run src/api/__tests__/marketWorkspace.test.ts src/components/market-home/__tests__/MarketEventReactionPanelV136.test.tsx
```

### Task 4: 首页延迟接线与本地配置

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`
- Modify: `.env.example`
- Modify: `docs/superpowers/platform-production-env.example`
- Local-only: `.env`

- [x] **Step 1: 写失败接线测试**

验证：
- V136 面板位于 V135 真实日历之后、V133 本地关注复盘之前。
- 面板挂载后独立请求，不阻塞首页和 V135。
- 请求失败仍保留日历、事件和个股查询。
- 游客与登录用户使用同一公开数据，不上传用户标识、自选或关注状态。

- [x] **Step 2: 运行测试确认失败**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx
```

- [x] **Step 3: 接线并启用本地开关**

安全默认值：

```text
PLATFORM_PUBLIC_EVENT_REACTIONS_V136_ENABLED=false
```

本地忽略的 `.env` 设置为 `true`，生产模板保持 `false`。

- [x] **Step 4: 运行接线回归**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

### Task 5: V136 verifier、发布包与文档

**Files:**
- Create: `scripts/verify_platform_observed_event_reactions_v136.py`
- Create: `tests/test_platform_observed_event_reactions_v136_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] verifier 检查安全代码规范化、事件上限、观察窗口、并发、超时、缓存、陈旧降级、响应体上限和独立限流。
- [x] verifier 固化 45 日历史事件输入、事件日收盘基线、事件日前 5 日量能基线、市场时区保护、强制匿名限流、后端不解析身份、事件源全不可用时不伪装空结果、32 代码历史缓存、64 键日历缓存和 4096 身份限流桶上限。
- [x] verifier 固化市场交易日对齐、停牌目标日不可用、跨巨潮报告期/FOMC 年份、72 条单来源缓存、部分来源失败保留成功数据、免 AI/仅资讯响应前端拒绝展示，以及限流桶容量满时不淘汰活跃身份。
- [x] verifier 禁止 AI、API Key、数据库写入、通知、因果结论、影响评级、目标价、收益预测、买卖及仓位建议。
- [x] verifier 运行前后端聚焦测试，成功输出 `DSA_PLATFORM_OBSERVED_EVENT_REACTIONS_V136_OK`。
- [x] 发布包 verifier 覆盖全部 V136 dirty 文件。
- [x] 文档明确 Yahoo Chart 为无密钥公开通道，不包装成官方授权或交易所实时数据。

### Task 6: 完整验收、浏览器回归与 Git 收口

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-dsa-v136-observed-event-market-reactions.md`

- [x] 运行相关后端 unittest、V126-V136 verifier、全量前端 Vitest、lint、生产构建、V1 operability、V2 readiness 和 release package gate。
- [x] 重启 8018，确认 `/health` 为 200；公开 V136 端点 `ai_used=false`、最多 6 个事件，并有缓存或诚实降级状态。
- [x] 浏览器验收游客、中英文、1/3/5/20 日控件、查询跳转和桌面布局；当前实时公开源只在总等待预算内返回美股事件，A股/港股/美股计算、登录用户公共契约、空状态和 390px 响应式边界由确定性 API/前端测试覆盖。
- [x] 确认游客私有请求保持休眠、登录用户既有私有接口回归正常、浏览器无应用级错误，1280px 实测无横向溢出。
- [x] 敏感令牌扫描 0 命中，`git diff --check` 通过。
- [x] 显式暂存 V136 文件并本地提交；最终工作树干净，不删除数据库、历史报告或用户数据。
- [x] 本阶段不推送 V136、不创建 PR、不启用真实支付、生产密钥或生产部署。

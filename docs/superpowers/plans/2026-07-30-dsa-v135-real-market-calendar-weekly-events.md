# DSA V135 真实市场日历与本周市场大事实实施计划

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 在 V134 本地提醒框架上接入 A股、港股、美股真实公开日历数据，让游客和免费用户无需 AI 或密钥即可查看今日事件、本周大事和自选相关事件。

**Architecture:** 新增独立的 `PublicMarketCalendarService`，并行读取巨潮资讯定期报告预约、Yahoo/yfinance 港美股财报与除息日历，以及美联储 FOMC 官方日历。每个来源使用独立缓存、超时和陈旧缓存降级；`PublicMarketHomeService` 只负责把已结构化的计划事件与既有公开新闻事件合并。前端新增 V135 日历面板，复用 V134 本地已读和 1/3/5/20 日复盘节点，并提供“今日、本周、我的日历、待复盘”视图。

**Tech Stack:** Python 3.12、requests、BeautifulSoup、yfinance、FastAPI/Pydantic、React 19、TypeScript、Vitest、Testing Library、Vite、8018 真实浏览器验收。

**Product boundary:** 仅展示来源明确给出的计划日期、公开资讯和用户本地复盘节点；不推断事件对行情的影响，不生成目标价、收益预测、买卖建议、仓位或交易指令。公开首页不调用 AI，不要求用户 API Key，不上传本地提醒状态。

---

### Task 1: 三市场真实日历数据服务

**Files:**
- Create: `src/services/public_market_calendar_service.py`
- Create: `tests/test_public_market_calendar_service_v135.py`

- [x] **Step 1: 写失败测试**

覆盖以下行为：

```python
service = PublicMarketCalendarService(
    cninfo_loader=fake_cninfo,
    yahoo_loader=fake_yahoo,
    fomc_loader=fake_fomc,
    clock=lambda: 100.0,
)
payload = service.load(sections, "2026-07-30T00:00:00Z")
assert {item["market"] for item in payload} == {"cn", "hk", "us"}
assert all(item["time_kind"] == "scheduled" for item in payload)
assert all(item["classification_source"] == "provider_schedule" for item in payload)
```

同时验证：

- 巨潮资讯使用最后一次有效预约日期，忽略已实际披露记录，统一 A股交易所后缀。
- Yahoo/yfinance 只读取日期，不展示盈利或收入预测数值。
- FOMC 只解析美联储官网明确列出的会议日期。
- 仅保留最近 7 日和未来 30 日，最多 36 条；可见热门证券优先但不伪装成全市场排名。
- 三来源并行，单来源超时或异常不影响其他市场。
- 命中缓存时标为 `cached`；刷新失败时可使用有界陈旧缓存并标为 `stale`。
- URL 只接受 HTTP/HTTPS；事件 ID 稳定；不调用 AI、不读取 API Key、不写数据库。

- [x] **Step 2: 运行测试并确认模块不存在**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_calendar_service_v135
```

- [x] **Step 3: 实现最小服务**

服务接口：

```python
class PublicMarketCalendarService:
    def load(
        self,
        sections: Sequence[Dict[str, Any]],
        as_of: str,
    ) -> List[Dict[str, Any]]:
        ...
```

公开来源：

- A股：`https://www.cninfo.com.cn/new/information/getPrbookInfo`
- 港股/美股：本地依赖 `yfinance.Ticker(symbol).calendar`
- 宏观：`https://www.federalreserve.gov/monetarypolicy/fomccalendars.htm`

缓存默认 900 秒，陈旧缓存最多保留 21600 秒，整体等待上限 4 秒。来源失败只能降级，不得让 `/api/v1/market-workspace/home` 失败。

- [x] **Step 4: 运行测试并确认通过**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_calendar_service_v135
```

### Task 2: 公共首页数据契约与事件合并

**Files:**
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `src/services/public_market_home_service.py`
- Modify: `tests/test_public_market_home_v116.py`

- [x] **Step 1: 写失败集成测试**

验证：

- `MarketEventTimeKind` 接受 `scheduled`。
- `PublicMarketEvent` 接受 `classification_source="provider_schedule"` 和受限 `schedule_type`。
- V135 开关开启时，真实计划事件与 V126 新闻事件合并、去重并限制总量。
- V135 开关关闭时不执行日历加载器，V116 旧行为保持不变。
- 日历加载器抛错时返回新闻事件，并在市场 warnings 中加入 `market_calendar_unavailable`。

- [x] **Step 2: 运行测试并确认失败**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116
```

- [x] **Step 3: 完成最小接线**

新增安全开关：

```text
PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED=false
```

本地 `.env` 启用，`.env.example` 和生产模板保持关闭。合并时计划事件优先，相同 `event_id` 只保留一条；首页事件总数不得超过 48。

- [x] **Step 4: 运行后端聚焦回归**

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_calendar_service_v135 tests.test_public_market_event_service tests.test_public_market_home_v116
```

### Task 3: V135 今日、本周与我的日历界面

**Files:**
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/components/market-home/marketEventCalendarV134.ts`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/marketEventCalendarV134.test.ts`
- Create: `apps/dsa-web/src/components/market-home/MarketEventCalendarPanelV135.tsx`
- Create: `apps/dsa-web/src/components/market-home/__tests__/MarketEventCalendarPanelV135.test.tsx`

- [x] **Step 1: 写失败前端测试**

覆盖：

- `timeKind="scheduled"` 直接使用来源日期，不再依赖标题正则。
- 默认显示本周，支持今日、本周、我的日历和待复盘。
- A股财报、港美股财报、除息日和 FOMC 使用中英文系统文案，不混入另一种界面语言。
- 显示来源、数据状态、计划日期、市场和查询按钮。
- 无计划事件、陈旧来源、缺少代码和移动端长文本安全降级。
- 明确显示“公开数据、未使用 AI”“事件与行情不代表因果关系”“不构成投资建议”。

- [x] **Step 2: 运行测试并确认组件不存在**

```powershell
cd apps/dsa-web
npm.cmd run test -- --run src/components/market-home/__tests__/marketEventCalendarV134.test.ts src/components/market-home/__tests__/MarketEventCalendarPanelV135.test.tsx
```

- [x] **Step 3: 实现 V135 面板**

V135 复用 V134 的本地作用域、已读状态和复盘节点，不新增网络请求。默认“本周”按 UTC 日期窗口展示未来 7 日及今日；“我的日历”包含自选匹配和关注事件。

- [x] **Step 4: 运行前端聚焦测试**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/marketEventCalendarV134.test.ts src/components/market-home/__tests__/MarketEventCalendarPanelV135.test.tsx
```

### Task 4: 首页接线与本地配置

**Files:**
- Modify: `apps/dsa-web/src/components/market-home/DailyMarketEventCenterV126.tsx`
- Modify: `apps/dsa-web/src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Modify: `.env.example`
- Modify: `docs/superpowers/platform-production-env.example`
- Local-only: `.env`

- [x] **Step 1: 写失败接线测试**

验证 V135 面板替换 V134 展示入口，V133 关注后的复盘节点仍即时出现，查询按钮继续调用既有 `onOpenSymbol`，游客无需登录。

- [x] **Step 2: 运行测试并确认失败**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

- [x] **Step 3: 完成接线并启用本地开关**

生产模板默认关闭，本地 `.env` 设置：

```text
PLATFORM_PUBLIC_MARKET_CALENDAR_V135_ENABLED=true
```

不修改真实支付、生产密钥、数据库和用户数据。

- [x] **Step 4: 运行接线回归**

```powershell
npm.cmd run test -- --run src/components/market-home/__tests__/DailyMarketEventCenterV126.test.tsx src/pages/__tests__/HomePage.test.tsx
```

### Task 5: V135 verifier、发布包与文档

**Files:**
- Create: `scripts/verify_platform_real_market_calendar_v135.py`
- Create: `tests/test_platform_real_market_calendar_v135_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] verifier 检查三来源、4 秒超时、缓存和陈旧降级、36/48 容量上限、`scheduled` 契约和安全开关。
- [x] verifier 禁止 AI、API Key、数据库写入、投资建议、目标价、收益预测和交易指令。
- [x] verifier 运行后端与前端聚焦测试，成功输出 `DSA_PLATFORM_REAL_MARKET_CALENDAR_V135_OK`。
- [x] 发布包 verifier 覆盖全部 V135 dirty 文件。
- [x] 文档记录数据源边界：巨潮和美联储为官方公开源；Yahoo/yfinance 为无密钥公开数据通道，不包装成官方授权数据。

### Task 6: 完整验收、服务重启与 Git 收口

**Files:**
- Modify: `docs/superpowers/plans/2026-07-30-dsa-v135-real-market-calendar-weekly-events.md`

- [x] 运行相关后端 unittest、V126-V135 verifier、全量前端 Vitest、lint、生产构建和 release package gate。
- [x] 重启 8018，确认 `/health` 为 200，真实首页返回 `provider_schedule` 事件和 `ai_used=false`。
- [x] 浏览器验收游客、登录用户、中英文、A股/港股/美股、今日/本周/我的日历/待复盘、查询跳转、桌面和移动端。
- [x] 确认浏览器控制台无应用错误、无横向溢出、冷启动有界、缓存刷新更快、失败来源诚实降级；游客仅保留预期的登录态探测 401。
- [x] 敏感令牌扫描 0 命中，`git diff --check` 通过。
- [x] 显式暂存 V135 文件并本地提交；最终工作树干净，不删除数据库、历史报告或用户数据。
- [x] 本阶段不推送 V135、不创建 PR、不启用真实支付、生产密钥或生产部署。

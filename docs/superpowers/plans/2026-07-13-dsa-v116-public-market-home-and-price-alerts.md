# DSA V116 首页市场吸引面与会员精确到价提醒 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让游客打开 DSA 首页立即看到 A股、港股、美股的最新可用市场数据和客观活跃股票，并让注册用户能够设置“价格高于/低于指定值”的私有提醒，由后台持续监控并在网站内保存触发通知，同时保持 API 可被未来 APP 复用。

**Architecture:** 复用 V113 `/market` 工作台、V115 统一事实快照和 V100 私有提醒表，不建立第三套行情、账号或提醒系统。新增一个聚合三市场的公开首页 API、一个可复用首页市场组件、两类精确到价规则、单进程后台监控 worker 和用户私有提醒事件收件箱；所有行情继续携带来源、时间、新鲜度和展示模式，未取得再分发授权前只显示“最新可用/延迟”而不宣称实时。

**Tech Stack:** Python 3.12、FastAPI、SQLAlchemy/SQLite、React 19、TypeScript、Vite、Vitest、Playwright、现有 DSA `BasicQueryService`、`MarketWorkspaceService`、平台账号/自选/提醒 API。

---

## 1. 执行前必须理解的当前真相

### 1.1 已有能力

- V113 已实现公开 `/market` 页面和以下游客接口：
  - `GET /api/v1/market-workspace/overview?market=cn|hk|us`
  - `GET /api/v1/market-workspace/search`
  - `GET /api/v1/market-workspace/symbol/{symbol}`
- V113 已有 A股、港股、美股行情卡片、涨跌列表、热力图、搜索和股票工作台。
- V100 已有按 `platform_user_id` 隔离的私有提醒规则、雷达运行和触发事件表。
- V115 已把 `BasicQueryService` 定为股票事实快照主入口；V116 不得绕开统一事实快照再次直接抓取同一股票。
- 首页已有平台注册、登录、免费额度、自选和分析入口；V116 应最小接入，不重写整页身份系统。

### 1.2 当前缺口和根因

1. `/market` 是独立页面，首页初次进入仍以查询为主，游客不能第一眼看到三地市场内容。
2. `MarketWorkspaceService` 当前只在预设股票集合中排序，不能称为“全市场热门榜”。
3. `SymbolWorkspaceV113.tsx` 提交 `price_above` / `price_below`，但 `ALERT_RULE_TYPES` 不包含这两个值，后端会返回 `invalid_alert_rule`。
4. V100 规则只在用户主动运行雷达时评估，不是网页关闭后仍运行的持续到价提醒。
5. 独立 `/api/v1/alerts` 告警中心支持 `price_cross` 和通知 worker，但表没有 `platform_user_id`，属于管理员/部署者告警能力，不能直接暴露给普通会员。
6. V100 付费判断只识别旧的 `pro/premium/enterprise`，尚未同时识别正式会员名 `plus/pro/max`。

### 1.3 V116 明确不做

- 不开发 iOS、Android 或新的桌面客户端；只提供网站功能和稳定 API 契约。
- 不增加 APNs、FCM、短信、WhatsApp 或会员个人邮件发送；V116 先完成持久化站内提醒，未来 APP 读取同一事件 API。
- 不把管理员 `/api/v1/alerts` 改造成会员系统，也不删除该系统。
- 不采购、签署或模拟任何市场数据授权合同。
- 不从免费网页抓取数据后宣称“实时”。
- 不新增 Redis、Celery、Kafka、MongoDB、第二套用户表或第二套自选表。
- 不改变 V112 API 次数、加油包、BYOK 和本地模型规则。
- 不把用户自定义提醒称为平台目标价、买卖信号或投资建议。

## 2. 用户流程与产品文案

```text
游客打开首页
  -> 同时看到 A股 / 港股 / 美股市场条带与关注股票
  -> 查看价格、涨跌、数据时间、来源和是否延迟
  -> 点击股票打开现有股票工作台
  -> 点击“到价提醒”
  -> 未注册：保留股票、方向和价格草稿，滚动到现有注册区
  -> 注册完成：恢复草稿并要求用户最终确认
  -> 保存私有提醒
  -> 后台 worker 持续读取最新可用行情
  -> 真正穿越用户阈值时写入私有提醒事件
  -> 网站提醒铃显示未读数量；未来 APP 调用同一 API
```

首页中文固定使用以下表达：

- 模块标题：`三地市场速览`
- 股票列表：`市场关注` 或 `活跃变化`
- 数据标签：`最新可用价格`、`延迟行情`、`更新时间`
- 按钮：`查看股票`、`到价提醒`
- 注册利益：`注册后每周赠送 5 次快速分析及 1 次深度分析，首月额外赠送 1 次深度分析。`
- 合规说明：`仅提供市场资讯、客观数据和用户自定义提醒，不构成投资建议。`

禁止使用：

- `热门推荐`
- `建议买入`
- `建议卖出`
- `平台目标价`
- 未经授权时的 `实时股价`

## 3. API 契约

### 3.1 公开首页市场 API

```http
GET /api/v1/market-workspace/home
```

响应必须保持 `ai_used=false`：

```json
{
  "as_of": "2026-07-13T01:30:00+00:00",
  "markets": [
    {
      "market": "hk",
      "session_state": "open",
      "display_mode": "latest_available",
      "ranking_scope": "configured_universe",
      "selection_basis": "turnover_then_absolute_change",
      "indices": [],
      "attention": [],
      "sources": [],
      "warnings": []
    }
  ],
  "ai_used": false,
  "informational_only": true
}
```

规则：

- `markets` 顺序固定为 `cn`、`hk`、`us`。
- 某市场失败时仍返回其他市场，并在该市场 `warnings` 中加入稳定错误码。
- `ranking_scope=configured_universe` 时，前端只能写“市场关注/活跃变化”，不能写“全市场热门”。
- `display_mode` 只允许 `latest_available`、`delayed`、`realtime`。
- 默认配置必须为 `latest_available`；代码、测试或文档不得把一个环境变量当作市场数据授权证明。
- 每个证券继续复用 V113 `MarketSecurityItem`，包含 `source_state`。

### 3.2 私有精确到价规则

继续使用：

```http
POST /api/v1/platform/watchlist/alert-rules
```

上涨到价：

```json
{
  "stockCode": "0700.HK",
  "ruleType": "price_above",
  "threshold": 500.0,
  "enabled": true
}
```

下跌到价：

```json
{
  "stockCode": "AAPL",
  "ruleType": "price_below",
  "threshold": 180.0,
  "enabled": true
}
```

触发语义：

- `price_above`：上次有效观察值 `< threshold`，本次有效观察值 `>= threshold`。
- `price_below`：上次有效观察值 `> threshold`，本次有效观察值 `<= threshold`。
- 第一次观察只建立基线，不触发。
- `freshness` 不是 `fresh` 时不触发，只更新失败/降级统计，不覆盖上一次有效价格。
- 同一用户、同一股票可以同时保存一条 `price_above` 和一条 `price_below`。
- 阈值必须是有限正数且不大于 `1_000_000_000`。
- 用户删除后沿用 V100 软停用语义。

### 3.3 私有提醒事件 API

```http
GET /api/v1/platform/watchlist/alert-events?unread_only=true&limit=20
POST /api/v1/platform/watchlist/alert-events/{event_id}/read
POST /api/v1/platform/watchlist/alert-events/read-all
```

单条事件：

```json
{
  "id": 81,
  "stock_code": "AAPL",
  "rule_type": "price_above",
  "direction": "above",
  "value": 201.25,
  "threshold": 200.0,
  "source": "authorized_or_public_source_name",
  "observed_at": "2026-07-13T01:30:00+00:00",
  "created_at": "2026-07-13T01:30:05+00:00",
  "read_at": null,
  "ai_used": false
}
```

所有列表和写操作必须按当前 `platform_user_id` 过滤；用户 A 对用户 B 的事件执行已读操作必须返回 `404`。

## 4. 文件结构锁定

### 4.1 新建文件

- `src/services/public_market_home_service.py`：聚合三市场首页数据，明确排序范围和展示模式。
- `src/services/platform_price_alert_worker.py`：后台批量检查精确到价规则并写入私有事件。
- `tests/test_public_market_home_v116.py`：公开首页 API、缓存、降级、排序和授权文案测试。
- `tests/test_platform_price_alert_worker_v116.py`：到价穿越、基线、数据降级、隔离和去重测试。
- `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`：首页三地市场模块。
- `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`：首页组件测试。
- `apps/dsa-web/src/components/alerts/PriceAlertFormV116.tsx`：市场页与首页共用的到价表单。
- `apps/dsa-web/src/components/alerts/__tests__/PriceAlertFormV116.test.tsx`：规则方向、阈值和登录状态测试。
- `apps/dsa-web/src/components/alerts/PriceAlertInboxV116.tsx`：站内提醒铃和私有事件列表。
- `apps/dsa-web/src/components/alerts/__tests__/PriceAlertInboxV116.test.tsx`：未读、已读、用户切换测试。
- `apps/dsa-web/src/components/layout/__tests__/ShellHeader.test.tsx`：提醒铃在全站页头的登录/游客集成测试。
- `apps/dsa-web/e2e/public-market-home-price-alerts-v116.spec.ts`：游客、注册、提醒和移动端浏览器验收。
- `scripts/verify_platform_public_market_price_alerts_v116.py`：V116 总验收器。
- `tests/test_platform_public_market_price_alerts_v116_verifier.py`：验收器缺文件和失败路径测试。

### 4.2 修改文件

- `src/storage.py`
- `src/platform_watchlist_automation.py`
- `src/config.py`
- `main.py`
- `api/middlewares/auth.py`
- `api/v1/schemas/market_workspace.py`
- `api/v1/schemas/platform.py`
- `api/v1/endpoints/market_workspace.py`
- `api/v1/endpoints/platform.py`
- `apps/dsa-web/src/api/marketWorkspace.ts`
- `apps/dsa-web/src/api/platform.ts`
- `apps/dsa-web/src/pages/HomePage.tsx`
- `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`
- `apps/dsa-web/src/components/market-workspace/SymbolWorkspaceV113.tsx`
- `apps/dsa-web/src/components/layout/ShellHeader.tsx`
- `apps/dsa-web/src/i18n/uiText.ts`
- `.env.example`
- `scripts/verify_platform_release_candidate_package.py`
- `tests/test_platform_release_candidate_package.py`
- `docs/alerts.md`
- `docs/superpowers/platform-product-rules.md`
- `docs/superpowers/platform-local-v1-acceptance-status.md`
- `docs/superpowers/platform-release-candidate-manifest.md`
- `docs/superpowers/platform-review-slices.md`
- `docs/CHANGELOG.md`

## 5. 实施任务

### Task 1: 先用测试锁定当前断裂契约和会员规则

**Files:**
- Modify: `tests/test_platform_watchlist_alert_loop_v100.py`
- Modify: `tests/test_market_workspace_v113.py`
- Modify: `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`

- [ ] **Step 1: 写后端失败测试，证明精确到价规则应被接受**

```python
def test_exact_price_rules_are_private_and_supported(self) -> None:
    service = PlatformWatchlistAutomationService(db_manager=self.db)
    above = service.save_rule(
        user_id=self.user_a.id,
        plan="free",
        stock_code="AAPL",
        rule_type="price_above",
        threshold=200.0,
    )
    below = service.save_rule(
        user_id=self.user_a.id,
        plan="free",
        stock_code="AAPL",
        rule_type="price_below",
        threshold=180.0,
    )
    assert {item["rule_type"] for item in above["items"] + below["items"]} >= {
        "price_above",
        "price_below",
    }
    assert service.list_rules(self.user_b.id, plan="free")["items"] == []
```

- [ ] **Step 2: 写阈值和套餐别名失败测试**

```python
def test_exact_price_threshold_and_paid_plan_aliases(self) -> None:
    service = PlatformWatchlistAutomationService(db_manager=self.db)
    for plan in ("plus", "pro", "max", "premium", "enterprise"):
        assert service.rule_limit(plan) == 50
    assert service.rule_limit("free") == 3
    with self.assertRaisesRegex(ValueError, "threshold"):
        service.save_rule(
            user_id=self.user_a.id,
            plan="free",
            stock_code="AAPL",
            rule_type="price_above",
            threshold=0,
        )
```

- [ ] **Step 3: 写前端失败测试，禁止把 400 误报成未登录**

```tsx
it('shows an invalid-rule error instead of a login prompt', async () => {
  saveWatchlistAlertRule.mockRejectedValue({ parsedError: { status: 400, message: 'invalid_alert_rule' } });
  renderMarketWorkspace();
  await userEvent.click(await screen.findByRole('button', { name: '保存条件提醒' }));
  expect(await screen.findByRole('alert')).toHaveTextContent('提醒保存失败');
  expect(screen.queryByText('登录后可保存条件提醒。')).not.toBeInTheDocument();
});
```

- [ ] **Step 4: 运行 RED**

```powershell
Set-Location E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_watchlist_alert_loop_v100 -v
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/pages/__tests__/MarketWorkspacePage.test.tsx
```

Expected: 后端因 `price_above` / `price_below` 不在允许集合而失败；前端因错误分支仍统一显示登录提示而失败。

- [ ] **Step 5: 记录基线但不修改实现**

保存 RED 输出到终端/PR 证据，不把临时日志或截图提交进仓库。

### Task 2: 扩展 V100 私有提醒模型和 SQLite 兼容迁移

**Files:**
- Modify: `src/storage.py`
- Modify: `src/platform_watchlist_automation.py`
- Modify: `api/v1/schemas/platform.py`
- Test: `tests/test_platform_watchlist_alert_loop_v100.py`

- [ ] **Step 1: 在模型中增加最小状态字段**

`PlatformWatchlistAlertRule` 增加：

```python
last_observed_value = Column(Float)
last_observed_at = Column(DateTime)
last_triggered_at = Column(DateTime)
```

`PlatformWatchlistRadarRun` 增加：

```python
run_kind = Column(String(32), nullable=False, default="radar", index=True)
```

`PlatformWatchlistAlertEvent` 增加：

```python
source = Column(String(64))
observed_at = Column(DateTime)
read_at = Column(DateTime, index=True)
```

- [ ] **Step 2: 增加现有 SQLite 数据库兼容列定义**

```python
_PLATFORM_ALERT_V116_COLUMN_SQL = {
    PlatformWatchlistAlertRule.__tablename__: {
        "last_observed_value": "FLOAT",
        "last_observed_at": "DATETIME",
        "last_triggered_at": "DATETIME",
    },
    PlatformWatchlistRadarRun.__tablename__: {
        "run_kind": "VARCHAR(32) NOT NULL DEFAULT 'radar'",
    },
    PlatformWatchlistAlertEvent.__tablename__: {
        "source": "VARCHAR(64)",
        "observed_at": "DATETIME",
        "read_at": "DATETIME",
    },
}
```

在 `DatabaseManager.initialize()` 的 `Base.metadata.create_all()` 后调用 `_ensure_platform_alert_v116_columns()`；实现方式沿用 `_ensure_platform_billing_v112_columns()` 的逐表检查和重复列容错。

- [ ] **Step 3: 扩展允许规则和付费套餐别名**

```python
ALERT_RULE_TYPES = {
    "price_above",
    "price_below",
    "price_move",
    "ma20_cross",
    "volume_change",
    "source_update",
    "data_quality",
}
PAID_PLANS = {"plus", "pro", "max", "premium", "enterprise"}
EXACT_PRICE_RULE_TYPES = {"price_above", "price_below"}
```

校验逻辑：

```python
if normalized_type in EXACT_PRICE_RULE_TYPES:
    if normalized_threshold is None or normalized_threshold <= 0 or normalized_threshold > 1_000_000_000:
        raise ValueError("threshold must be a finite positive price")
```

保存或修改精确到价阈值时必须清空 `last_observed_value`、`last_observed_at` 和 `last_triggered_at`，让新阈值重新建立基线。

- [ ] **Step 4: 扩展响应 DTO**

`PlatformWatchlistAlertRuleItem` 追加：

```python
last_observed_value: Optional[float] = None
last_observed_at: Optional[str] = None
last_triggered_at: Optional[str] = None
```

不得向前端返回数据库会话、内部锁、原始异常或用户邮箱。

- [ ] **Step 5: 运行 GREEN 和旧规则回归**

```powershell
Set-Location E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_watchlist_alert_loop_v100 -v
```

Expected: 原 V100 规则全部通过，新增两种规则通过，免费3条/付费50条语义保持不变。

### Task 3: 实现后台精确到价监控 worker

**Files:**
- Create: `src/services/platform_price_alert_worker.py`
- Create: `tests/test_platform_price_alert_worker_v116.py`
- Modify: `src/platform_watchlist_automation.py`
- Modify: `src/config.py`
- Modify: `.env.example`
- Modify: `main.py`

- [ ] **Step 1: 写穿越、首次基线和降级数据失败测试**

```python
def test_first_observation_sets_baseline_without_trigger(worker, quote_loader, rule):
    quote_loader.return_value = fresh_quote(price=199.0)
    stats = worker.run_once()
    assert stats == {"loaded": 1, "observed": 1, "triggered": 0, "degraded": 0, "failed": 0}
    assert rule.last_observed_value == 199.0


def test_price_above_triggers_only_on_cross(worker, quote_loader, rule):
    rule.last_observed_value = 199.0
    quote_loader.return_value = fresh_quote(price=200.5)
    stats = worker.run_once()
    assert stats["triggered"] == 1
    assert worker.events_for(rule.user_id)[0]["direction"] == "above"


def test_stale_quote_never_triggers(worker, quote_loader, rule):
    rule.last_observed_value = 199.0
    quote_loader.return_value = stale_quote(price=205.0)
    stats = worker.run_once()
    assert stats["triggered"] == 0
    assert stats["degraded"] == 1
    assert rule.last_observed_value == 199.0
```

- [ ] **Step 2: 写批量去重和用户隔离失败测试**

两个用户都监听 AAPL 时，单轮只调用一次 AAPL 行情加载器，但必须分别更新两名用户的规则；事件归属各自用户，互不可见。

- [ ] **Step 3: 实现 worker 主流程**

```python
class PlatformPriceAlertWorker:
    def run_once(self) -> Dict[str, int]:
        rules = self.repository.list_enabled_exact_price_rules(limit=self.max_rules_per_cycle)
        quotes = self._load_unique_symbols(rules)
        stats = {"loaded": len(rules), "observed": 0, "triggered": 0, "degraded": 0, "failed": 0}
        for rule in rules:
            quote = quotes.get(rule.stock_code)
            result = self._evaluate(rule, quote)
            self.repository.apply_observation(rule_id=rule.id, result=result)
            stats[result.status] += 1
        return stats
```

`_evaluate` 返回稳定结果对象，至少包含：`status`、`price`、`observed_at`、`source`、`direction`、`triggered`。禁止返回原始 provider 响应。

- [ ] **Step 4: 触发时复用现有 radar/event 表**

同一用户本轮存在一个或多个触发时：

1. 新建一条 `PlatformWatchlistRadarRun(run_kind="price_monitor")`，payload 只保存触发股票的脱敏事实字段。
2. 每条触发写入现有 `PlatformWatchlistAlertEvent` 并关联该 run。
3. V100 每日复盘历史查询只返回 `run_kind="radar"`，避免每分钟监控记录污染复盘时间线。
4. 更新规则的 `last_triggered_at` 和最新有效观察值。

- [ ] **Step 5: 增加安全默认配置**

```dotenv
PLATFORM_PRICE_ALERT_MONITOR_ENABLED=false
PLATFORM_PRICE_ALERT_MONITOR_INTERVAL_SECONDS=60
PLATFORM_PRICE_ALERT_MONITOR_MAX_RULES_PER_CYCLE=1000
PLATFORM_PRICE_ALERT_MONITOR_MAX_WORKERS=8
PLATFORM_PRICE_ALERT_MONITOR_QUOTE_TIMEOUT_SECONDS=3
```

`src/config.py` 对 interval 设置 `30..3600` 范围，对 max rules 设置 `1..10000`，对 workers 设置 `1..32`。

- [ ] **Step 6: 接入现有 schedule 模式**

在 `main.py` 的 `background_tasks` 中追加：

```python
if getattr(config, "platform_price_alert_monitor_enabled", False):
    price_alert_worker = PlatformPriceAlertWorker(config_provider=_reload_runtime_config)
    background_tasks.append({
        "task": price_alert_worker.run_once,
        "interval_seconds": config.platform_price_alert_monitor_interval_seconds,
        "run_immediately": True,
        "name": "platform_price_alert_monitor",
    })
```

不得把 worker 注册到每个 Uvicorn Web worker；本地和首版部署只允许一个 schedule 进程负责监控，文档必须明确该边界。

- [ ] **Step 7: 运行测试**

```powershell
Set-Location E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_price_alert_worker_v116 tests.test_platform_watchlist_alert_loop_v100 -v
```

Expected: 首次不误报、真实穿越触发一次、持续在线不重复、回穿后再次穿越可重新触发、stale/unavailable 不触发、同股票单轮只抓取一次。

### Task 4: 增加私有提醒事件收件箱 API

**Files:**
- Modify: `src/platform_watchlist_automation.py`
- Modify: `api/v1/schemas/platform.py`
- Modify: `api/v1/endpoints/platform.py`
- Modify: `apps/dsa-web/src/api/platform.ts`
- Test: `tests/test_platform_price_alert_worker_v116.py`
- Test: `apps/dsa-web/src/api/__tests__/platform.test.ts`

- [ ] **Step 1: 写 A/B 隔离和已读失败测试**

```python
def test_alert_event_feed_is_private(client_a, client_b, event_a, event_b):
    body_a = client_a.get("/api/v1/platform/watchlist/alert-events").json()
    assert [item["id"] for item in body_a["items"]] == [event_a.id]
    assert client_a.post(f"/api/v1/platform/watchlist/alert-events/{event_b.id}/read").status_code == 404
```

- [ ] **Step 2: 实现 DTO**

新增 `PlatformWatchlistAlertEventItem` 和 `PlatformWatchlistAlertEventsResponse`；响应包含 `user_id`、`total`、`unread`、`items`、`ai_used=false`。

- [ ] **Step 3: 实现 API**

```python
@router.get("/watchlist/alert-events", response_model=PlatformWatchlistAlertEventsResponse)
async def platform_watchlist_alert_events(
    request: Request,
    unread_only: bool = Query(False),
    limit: int = Query(20, ge=1, le=100),
):
    identity = _require_identity(request)
    return PlatformWatchlistAutomationService().list_alert_events(
        int(identity.user_id), unread_only=unread_only, limit=limit
    )
```

已读和全部已读使用 `_require_platform_csrf`、当前用户过滤和写限流。跨用户事件统一返回404。

- [ ] **Step 4: 实现 TypeScript API**

```ts
alertEvents: async (unreadOnly = false, limit = 20): Promise<PlatformWatchlistAlertEventsResponse> => {
  const response = await apiClient.get('/api/v1/platform/watchlist/alert-events', {
    params: { unread_only: unreadOnly, limit },
  });
  return toCamelCase<PlatformWatchlistAlertEventsResponse>(response.data);
},
markAlertEventRead: async (eventId: number) => {
  const response = await apiClient.post(`/api/v1/platform/watchlist/alert-events/${eventId}/read`);
  return toCamelCase<PlatformWatchlistAlertEventsResponse>(response.data);
},
markAllAlertEventsRead: async () => {
  const response = await apiClient.post('/api/v1/platform/watchlist/alert-events/read-all');
  return toCamelCase<PlatformWatchlistAlertEventsResponse>(response.data);
},
```

- [ ] **Step 5: 运行后端和前端 API 测试**

```powershell
Set-Location E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_price_alert_worker_v116 -v
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/api/__tests__/platform.test.ts
```

### Task 5: 修复市场工作台并复用统一到价表单

**Files:**
- Create: `apps/dsa-web/src/components/alerts/PriceAlertFormV116.tsx`
- Create: `apps/dsa-web/src/components/alerts/__tests__/PriceAlertFormV116.test.tsx`
- Modify: `apps/dsa-web/src/components/market-workspace/SymbolWorkspaceV113.tsx`
- Modify: `apps/dsa-web/src/pages/MarketWorkspacePage.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Test: `apps/dsa-web/src/pages/__tests__/MarketWorkspacePage.test.tsx`

- [ ] **Step 1: 写共享表单失败测试**

覆盖：高于、低于、空值、0、负数、非有限值、保存中、成功、401、400、429；401 才显示注册提示，400 显示规则错误，429 显示稍后重试。

- [ ] **Step 2: 定义共享组件契约**

```ts
export type ExactPriceRuleType = 'price_above' | 'price_below';

export type PriceAlertDraft = {
  stockCode: string;
  stockName: string;
  ruleType: ExactPriceRuleType;
  threshold: number;
  currency?: string | null;
};

type Props = {
  language: 'zh' | 'en';
  stockCode: string;
  stockName: string;
  currentPrice?: number | null;
  currency?: string | null;
  onSave: (draft: PriceAlertDraft) => Promise<void>;
};
```

- [ ] **Step 3: 用共享组件替换 V113 内联表单**

`SymbolWorkspaceV113` 保留行情、图表和资料，只把到价表单委托给 `PriceAlertFormV116`。不得在 V113 组件中维护第二份阈值校验。

- [ ] **Step 4: 修复错误分类**

`MarketWorkspacePage` 使用 `getParsedApiError`：

```ts
const parsed = getParsedApiError(error);
if (parsed.status === 401) {
  setLoginRequired(true);
  setActionNotice(en ? 'Sign in to save this alert.' : '登录后可保存到价提醒。');
} else {
  setActionNotice(en ? 'Alert could not be saved.' : '提醒保存失败，请检查价格后重试。');
}
```

- [ ] **Step 5: 运行组件和页面测试**

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/alerts/__tests__/PriceAlertFormV116.test.tsx src/pages/__tests__/MarketWorkspacePage.test.tsx
```

- [ ] **Step 6: 支持首页卡片直接打开股票工作台**

`MarketWorkspacePage` 读取 `location.search` 中的 `symbol`，通过现有规范化搜索结果或 `getSymbol` 打开对应股票。增加测试确认 `/market?symbol=AAPL` 首次渲染只加载一次 AAPL，并拒绝包含 `<`、`>`、`/`、`\` 或超过32字符的值。

### Task 6: 建立三市场公开首页聚合 API

**Files:**
- Create: `src/services/public_market_home_service.py`
- Create: `tests/test_public_market_home_v116.py`
- Modify: `api/v1/schemas/market_workspace.py`
- Modify: `api/v1/endpoints/market_workspace.py`
- Modify: `api/middlewares/auth.py`
- Modify: `.env.example`

- [ ] **Step 1: 写公开、无 AI、局部降级失败测试**

```python
def test_home_market_is_public_and_never_uses_ai(client):
    response = client.get("/api/v1/market-workspace/home")
    assert response.status_code == 200
    body = response.json()
    assert [item["market"] for item in body["markets"]] == ["cn", "hk", "us"]
    assert body["ai_used"] is False


def test_one_market_failure_does_not_blank_other_markets(service):
    body = service.build()
    assert body["markets"][0]["attention"]
    assert body["markets"][1]["warnings"] == ["market_home_unavailable"]
    assert body["markets"][2]["attention"]
```

- [ ] **Step 2: 写并发截止、排序范围和展示模式失败测试**

三个市场必须并行加载，总截止时间不超过配置值；一个加载器超时后按不可用市场返回，不能等待三个市场顺序超时。`ranking_scope` 必须为 `configured_universe`；有成交额时按成交额降序，无成交额时按绝对涨跌幅降序；缺失数字排最后。默认 `display_mode` 必须为 `latest_available`。

- [ ] **Step 3: 实现聚合服务**

```python
from concurrent.futures import ThreadPoolExecutor, wait
from datetime import datetime, timezone
from typing import Any, Callable, Dict, Optional

from src.services.market_workspace_service import MarketWorkspaceService


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


MARKETS = ("cn", "hk", "us")
_HOME_EXECUTOR = ThreadPoolExecutor(max_workers=3, thread_name_prefix="public-market-home")

class PublicMarketHomeService:
    def __init__(
        self,
        workspace_service: MarketWorkspaceService,
        *,
        timeout_seconds: float = 3.5,
        clock: Callable[[], str] = _utc_now,
        executor: Optional[ThreadPoolExecutor] = None,
    ) -> None:
        self.workspace_service = workspace_service
        self.timeout_seconds = max(1.0, min(float(timeout_seconds), 10.0))
        self.clock = clock
        self.executor = executor or _HOME_EXECUTOR

    def build(self) -> Dict[str, Any]:
        futures = {
            market: self.executor.submit(self.workspace_service.get_overview, market)
            for market in MARKETS
        }
        completed, _ = wait(futures.values(), timeout=self.timeout_seconds)
        sections = [
            self._section(market, futures[market].result())
            if futures[market] in completed and futures[market].exception() is None
            else self._unavailable_section(market)
            for market in MARKETS
        ]
        return {
            "as_of": self.clock(),
            "markets": sections,
            "ai_used": False,
            "informational_only": True,
        }
```

`_section` 最多返回6只 `attention` 股票，不能因为首页展示再逐股补请求；直接复用 V113 已有行情卡片和缓存。

- [ ] **Step 4: 增加配置化关注股票集合**

```dotenv
PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED=false
PLATFORM_PUBLIC_MARKET_HOME_CACHE_TTL_SECONDS=60
PLATFORM_PUBLIC_MARKET_HOME_TIMEOUT_SECONDS=3.5
PLATFORM_PUBLIC_MARKET_HOME_MAX_ITEMS_PER_MARKET=6
PLATFORM_PUBLIC_MARKET_HOME_SYMBOLS_CN=601318.SH,600519.SH,000001.SZ,300750.SZ
PLATFORM_PUBLIC_MARKET_HOME_SYMBOLS_HK=0700.HK,9988.HK,3690.HK,1299.HK
PLATFORM_PUBLIC_MARKET_HOME_SYMBOLS_US=AAPL,MSFT,NVDA,AMZN,TSLA
PLATFORM_MARKET_DATA_DISPLAY_MODE=latest_available
```

解析后按市场去重，每市场上限20个；空配置回退到 V113 当前安全集合。配置值只是关注集合，不是推荐名单。首页服务使用最多3个市场并发 worker，并在 `1..10` 秒范围内校验总截止时间。

- [ ] **Step 5: 挂载公开路由和匿名限流**

将 `/api/v1/market-workspace/home` 加入 `_public_market_workspace_path`。新增 `_require_home_enabled()`，只有 V113 和 V116 两个功能开关都开启时才提供首页聚合；关闭时返回404且不影响 `/market`。调用 `check_platform_rate_limit(request, "market_workspace_home", user_id=...)`，游客限流不保存完整 IP。

- [ ] **Step 6: 运行测试**

```powershell
Set-Location E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116 tests.test_market_workspace_v113 -v
```

### Task 7: 把三市场内容放到首页首屏并保留注册草稿

**Files:**
- Create: `apps/dsa-web/src/components/market-home/PublicMarketHomeV116.tsx`
- Create: `apps/dsa-web/src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx`
- Modify: `apps/dsa-web/src/api/marketWorkspace.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Test: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: 增加 API 类型和方法**

```ts
export type PublicMarketHomeSection = {
  market: MarketCode;
  sessionState: 'open' | 'closed' | 'unknown';
  displayMode: 'latest_available' | 'delayed' | 'realtime';
  rankingScope: 'configured_universe' | 'market_wide';
  selectionBasis: string;
  indices: MarketSecurityItem[];
  attention: MarketSecurityItem[];
  sources: DataSourceState[];
  warnings: string[];
};

getHome: async (): Promise<PublicMarketHomeResponse> => {
  const response = await apiClient.get('/api/v1/market-workspace/home');
  return toCamelCase<PublicMarketHomeResponse>(response.data);
},
```

- [ ] **Step 2: 写首页组件测试**

覆盖：

- 初始显示三市场，不需要先输入股票。
- 每张股票卡显示价格、涨跌、更新时间和来源状态。
- `rankingScope=configured_universe` 时标题为“市场关注”，不出现“全市场热门”。
- `displayMode=latest_available` 时不出现“实时股价”。
- 一个市场失败不隐藏其他市场。
- 390px 宽度无横向滚动。
- 点击股票进入 `/market?symbol=...`，不消耗 AI。

- [ ] **Step 3: 实现首页组件**

组件只负责展示和动作回调：

```ts
type Props = {
  language: 'zh' | 'en';
  data: PublicMarketHomeResponse | null;
  loading: boolean;
  onOpenSymbol: (symbol: string) => void;
  onCreateAlert: (draft: PriceAlertDraft) => void;
};
```

桌面端三列，移动端市场标签切换后单列。颜色之外必须显示 `+1.25%/-1.25%` 文本。点击“到价提醒”后在当前股票卡片下展开共用 `PriceAlertFormV116`，不得在首页组件内复制另一份方向和阈值校验。

- [ ] **Step 4: 最小修改 HomePage**

在现有主查询和注册区域之前渲染 `PublicMarketHomeV116`。首页只新增：加载状态、数据状态、打开股票回调、待注册提醒草稿和恢复逻辑；不得把市场组件的表格、排序或表单代码直接塞进 `HomePage.tsx`。

- [ ] **Step 5: 保存并恢复注册草稿**

草稿只存于内存和 `sessionStorage`，键为 `dsa_v116_pending_price_alert`；结构必须经过 `PriceAlertDraft` 校验，30分钟过期，不保存邮箱、密码、API Key 或 Cookie。

未登录点击到价提醒时：

1. 保存草稿。
2. 调用现有 `setAuthMode('register')`。
3. 滚动并聚焦现有平台注册邮箱输入框。
4. 注册成功后恢复草稿，展示最终确认表单；不得在注册完成瞬间静默创建提醒。

- [ ] **Step 6: 固定注册利益文案**

中文：

```text
注册后每周赠送 5 次快速分析及 1 次深度分析，首月额外赠送 1 次深度分析。
```

英文：

```text
Register to receive 5 quick analyses and 1 deep analysis each week, plus 1 extra deep analysis in the first month.
```

- [ ] **Step 7: 运行前端测试**

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/market-home/__tests__/PublicMarketHomeV116.test.tsx src/pages/__tests__/HomePage.test.tsx src/api/__tests__/marketWorkspace.test.ts
```

### Task 8: 增加全站站内提醒铃和 APP 可复用事件契约

**Files:**
- Create: `apps/dsa-web/src/components/alerts/PriceAlertInboxV116.tsx`
- Create: `apps/dsa-web/src/components/alerts/__tests__/PriceAlertInboxV116.test.tsx`
- Create: `apps/dsa-web/src/components/layout/__tests__/ShellHeader.test.tsx`
- Modify: `apps/dsa-web/src/components/layout/ShellHeader.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Modify: `docs/alerts.md`

- [ ] **Step 1: 写未读和用户切换失败测试**

测试登录后每60秒读取一次未读事件；登出、用户变化和组件卸载时取消旧轮询；旧用户慢响应不得覆盖新用户状态。

- [ ] **Step 2: 实现提醒铃**

```ts
type Props = {
  language: 'zh' | 'en';
};
```

- 每轮先调用现有 `platformApi.current()` 识别当前平台用户；401 视为游客并停止该轮私有事件请求。
- 同一用户会话内缓存用户ID；每60秒重新确认会话，识别注册、登录、退出和A/B切换。
- 未读数大于0显示徽标，超过99显示 `99+`。
- 展开后显示股票、方向、触发价格、用户阈值、来源和观察时间。
- 点击单条调用已读 API；“全部已读”调用 read-all API。
- 请求失败保留上次内容并显示可重试状态，不清空为0。
- 不使用浏览器原生 Notification 权限，不注册 Service Worker。

- [ ] **Step 3: 接入 ShellHeader 并写集成测试**

`ShellHeader` 直接渲染 `PriceAlertInboxV116`，组件自行通过 `/platform/me` 识别平台会话，不读取 HomePage 私有 state。`ShellHeader.test.tsx` 覆盖游客无私有事件请求、登录用户显示未读徽标以及路由切换后提醒铃仍存在。

- [ ] **Step 4: 在文档中固定 APP 复用边界**

`docs/alerts.md` 写明：

- Web、PWA、桌面壳和未来移动 APP 使用同一提醒规则/事件 API。
- V116 当前 Cookie 会话适用于 Web/PWA；原生 APP 的短期访问令牌、刷新令牌、Keychain/Keystore 和 APNs/FCM 属于独立认证/推送项目。
- APP 不得在本地复制提醒规则或自行轮询第三方行情。
- 服务端事件是唯一提醒真源。

- [ ] **Step 5: 运行组件测试**

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/alerts/__tests__/PriceAlertInboxV116.test.tsx src/components/layout/__tests__/ShellHeader.test.tsx
```

### Task 9: 验收器、长期文档、真实浏览器与 Git 收口

**Files:**
- Create: `scripts/verify_platform_public_market_price_alerts_v116.py`
- Create: `tests/test_platform_public_market_price_alerts_v116_verifier.py`
- Create: `apps/dsa-web/e2e/public-market-home-price-alerts-v116.spec.ts`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 实现 V116 验收器**

验收器依次运行：

1. V116 首页后端测试。
2. V116 精确到价 worker 和私有事件测试。
3. V100、V113、V115 相关回归。
4. V116 前端 API、组件、HomePage 和 MarketWorkspacePage 测试。
5. `npm run lint`。
6. `npm run build`。
7. release-candidate package gate。
8. 敏感信息扫描和禁止宣传扫描。

全部通过后只打印一次：

```text
DSA_PLATFORM_PUBLIC_MARKET_PRICE_ALERTS_V116_OK markets=cn,hk,us guest_home=true exact_price_alerts=true background_monitor=true private_events=true ai_required=false realtime_claim=false
```

- [ ] **Step 2: 增加禁止宣传扫描**

当默认 `PLATFORM_MARKET_DATA_DISPLAY_MODE=latest_available` 时，V116 首页组件不得出现 `实时股价`、`real-time price`、`全市场热门推荐`。扫描只针对 V116 用户文案，不误伤内部技术注释和既有授权说明文档。

- [ ] **Step 3: 真实浏览器验收**

在重启后的 `http://127.0.0.1:8018/?dsa_v116_smoke=1` 完成：

1. 游客中文：无需查询即看到三地市场和股票卡片。
2. 游客英文：英文文案完整，无中文业务残留。
3. 关闭一个市场加载器：另两个市场继续显示，失败市场明确降级。
4. 游客点击 AAPL 到价提醒：保留草稿并进入注册区。
5. 注册用户保存 `price_above`，刷新页面后仍存在。
6. 用户 A/B：互相看不到规则、事件和未读数。
7. 模拟第一次199、第二次201、阈值200：第一次无事件，第二次仅一条事件。
8. 模拟 stale 205：不得触发。
9. 390x844、768x1024、1440x900：无横向溢出、无遮挡、无空白首屏。
10. 浏览器 console 无未处理异常，network 和页面不出现密钥、Cookie 或原始异常。

- [ ] **Step 4: 更新长期文档**

`docs/CHANGELOG.md` 的 `[Unreleased]` 只增加扁平条目：

```markdown
- [新功能] 首页增加A股、港股、美股市场速览和注册转化入口
- [修复] 修复市场工作台精确到价提醒前后端规则不一致
- [新功能] 增加用户私有到价监控和站内提醒事件收件箱
- [测试] 增加V116首页、后台监控、用户隔离和浏览器验收门禁
```

验收状态必须写“本地验收”，不能升级成市场数据授权、生产部署、APP发布或支付上线证明。

- [ ] **Step 5: 执行最终门禁**

```powershell
Set-Location E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_public_market_home_v116 tests.test_platform_price_alert_worker_v116 tests.test_platform_watchlist_alert_loop_v100 tests.test_market_workspace_v113 -v
E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_unified_market_data_v115.py
E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_public_market_price_alerts_v116.py
E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_release_candidate_package.py
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/market-home src/components/alerts src/pages/__tests__/HomePage.test.tsx src/pages/__tests__/MarketWorkspacePage.test.tsx src/api
npm run lint
npm run build
Set-Location E:\DSA项目
git diff --check
git diff --cached --check
git status --short --untracked-files=all
```

- [ ] **Step 6: 遵守 Git 护栏**

未经潘总明确授权：

- 不执行 `git commit`。
- 不执行 `git push`、`git tag`。
- 不使用 `git add -A`。
- 不使用 `git reset --hard`、`git checkout --`、`git clean -fd`。
- 不覆盖、回退、暂存或提交其他窗口的改动。

## 6. 完成判定

V116 只有同时满足以下条件才能标记完成：

1. 游客打开首页无需输入股票即可看到 A股、港股、美股可用市场内容。
2. 首页没有因一个市场失败而整体空白。
3. 首页股票明确显示数据来源、时间、新鲜度和展示模式。
4. 配置关注集合不能冒充全市场热门榜。
5. 未取得数据授权时不显示“实时股价”。
6. 注册入口明确显示已确认的免费分析权益。
7. `price_above` / `price_below` 能由普通平台用户成功保存。
8. 到价规则、观察状态和触发事件均按用户隔离。
9. 首次观察不误报，真实穿越才触发，过期/缺失行情不触发。
10. 用户关闭网页后，单独 schedule 进程仍能持续监控并保存事件。
11. 网站提醒铃可以读取、单条已读和全部已读。
12. Web 和未来 APP 复用同一后端规则与事件 DTO，没有客户端私有规则真源。
13. 原管理员告警中心、V100其他规则、V113市场工作台和V115统一事实快照不回归。
14. 后端、前端、lint、build、verifier、release package、真实浏览器和 Git 检查全部通过。
15. 没有真实密钥、生产支付、生产部署、市场数据授权或 APP 发布的越权声明。

## 7. 回滚方案

1. 设置 `PLATFORM_PUBLIC_MARKET_HOME_V116_ENABLED=false`，首页隐藏三市场聚合，独立 `/market` 和既有查询继续可用。
2. 设置 `PLATFORM_PRICE_ALERT_MONITOR_ENABLED=false`，停止后台精确到价扫描；已保存规则和事件保留。
3. 前端隐藏 `PublicMarketHomeV116`、`PriceAlertFormV116` 和 `PriceAlertInboxV116`，不删除用户数据。
4. 新增列保持向后兼容；回滚代码不删除列、不重建表、不丢失已有 V100 规则和历史。
5. 若某市场来源不稳定，只降级该市场，不关闭其他市场或 AI 查询功能。

## 8. 交给开发 BOT 的连续目标指令

```text
/goal 按 E:\DSA项目\docs\superpowers\plans\2026-07-13-dsa-v116-public-market-home-and-price-alerts.md 完整执行 DSA V116。

目标：让游客打开 DSA 首页立即看到 A股、港股、美股最新可用市场数据和客观市场关注股票；让注册用户设置价格高于/低于指定值的私有提醒，由后台单独 schedule 进程持续监控并写入站内提醒事件；网站和未来 APP 复用同一 API。

执行要求：
1. 先读 E:\DSA项目\AGENTS.md、本计划、V100/V113/V115计划和当前 git status。
2. 保护现有工作树，不回退、不覆盖、不清理、不暂存其他窗口的改动。
3. 按 Task 1-9 顺序执行 TDD：先看到指定失败，再写最小实现，再跑当前任务和相关回归。
4. 复用 V113 市场工作台、V115统一事实快照和V100私有提醒表，不建立第三套行情、账号、自选或提醒系统。
5. 修复 price_above/price_below 前后端不一致；管理员 /api/v1/alerts 不开放给普通会员。
6. 默认只显示“最新可用价格”；未取得再分发授权不得宣传实时股价或全市场热门推荐。
7. 普通提醒必须按 platform_user_id 隔离；首次观察不触发；stale/unavailable 不触发；同股票每轮只抓取一次。
8. 首页和提醒失败不能影响既有免费查询、AI分析、BYOK、本地模型、自选和历史。
9. APP只复用API契约，本任务不开发移动客户端、不新增APNs/FCM或原生令牌认证。
10. 普通测试失败、8018旧进程、依赖或缓存问题自行诊断并继续，只有真实凭据、市场数据合同、生产动作或破坏性选择才暂停询问。
11. 未经潘总明确授权，不执行git commit、git push、git tag；禁止git add -A、git reset --hard、git checkout --、git clean -fd。

验收：
- 完成 Task 1-9 和全部完成判定。
- V116 verifier 输出 DSA_PLATFORM_PUBLIC_MARKET_PRICE_ALERTS_V116_OK。
- V100、V113、V115回归、前后端测试、lint、build、release package、真实浏览器、敏感信息和git diff检查全部通过。
- 最终报告列出修改文件、测试数量、worker运行证据、游客/注册用户/A-B隔离证据、三市场和移动浏览器证据、未验收的市场数据授权/生产/APP边界，以及完整git status。
```

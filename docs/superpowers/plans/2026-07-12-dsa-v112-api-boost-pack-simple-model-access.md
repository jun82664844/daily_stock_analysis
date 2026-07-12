# DSA V112 API 加油包与极简模型接入 Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 为 DSA 增加 HK$28 API 加油包、会员可选模型、极简 BYOK 接入和用户自有 Ollama 接入，让不熟悉 API、端口和模型名称的普通用户也能在三步以内完成设置。

**Architecture:** 复用现有平台账号、计费生命周期、额度流水、V111 请求级 BYOK 路由和分析主链，不再增加第二套账号或分析系统。V112-A 先交付加油包、统一模型目录和“选择供应商 → 粘贴 Key → 连接”的 Web 流程；V112-B 再交付只有连接状态的轻量本地连接器，通过出站 HTTPS 长轮询连接用户电脑上的 Ollama，不开发完整桌面版，也不让云端直接访问用户的 `localhost`。

**Tech Stack:** Python 3、FastAPI、SQLAlchemy、SQLite、Pydantic、React 19、TypeScript、Vitest、Testing Library、Playwright、PyInstaller、Windows Credential Manager。

---

## 1. 已确认的产品规则

### 1.1 API 加油包

- 商品代码固定为 `api_boost_168_28`。
- 售价固定为 HK$28。
- 每包增加 168 次 Flash + 28 次 Pro。
- 当前保守测算：成本 HK$19.68、贡献利润 HK$8.32、贡献利润率约 29.7%。
- 仅有效 PRO 和 MAX 会员可购买；游客、普通客户和 PLUS 不显示购买按钮。
- 加油包只增加次数，不升级会员等级、模型目录、并发、历史、自选、提醒或其他权益。
- 会员基础额度先扣，加油包额度后扣；Flash 和 Pro 分开计数，不能互换。
- 加油包最迟在当前会员月结束或会员 `expires_at` 到达时失效，以较早者为准。
- 未使用额度不退款、不折现、不转让、不结转。
- 距离失效不足 60 分钟时不再创建加油包结算，页面引导用户先续费，避免付款完成时额度已经失效。

### 1.2 模型选择权限

| 用户等级 | 平台模型 | 用户自己的 API | 用户自有本地模型 |
| --- | --- | --- | --- |
| 游客 | 仅系统默认免费体验 | 不开放 | 不开放 |
| 普通客户 | 系统默认 Flash；按免费额度使用 | 不开放 | 不开放 |
| PLUS | 保留普通客户免费模型 | 可从已连接 API 支持的获准模型中选择 | 可从已连接 Ollama 模型中选择 |
| PRO | 可选择 PRO 获准模型目录 | 可选择 | 可选择 |
| MAX | 可选择完整获准模型目录 | 可选择 | 可选择 |

规则：

- 用户不输入供应商 Base URL、不输入模型内部名称、不编辑 JSON。
- 页面只显示管理员批准并且运行时实际可用的模型。
- 每张模型卡显示中文名称、供应商、速度、适合用途和“消耗 1 Flash / 1 Pro / N Pro”。
- 默认选中“平台推荐”，用户不设置也能直接使用。
- 选择模型只改变本次及后续分析使用的模型，不改变会员等级。
- 模型下线后自动回到“平台推荐”，不得静默换成其他收费更高的模型。

### 1.3 极简 API 接入

用户只需要三步：

1. 选择 OpenAI、Claude 或 DeepSeek。
2. 粘贴 API Key。
3. 点击“连接并测试”。

页面不要求用户填写模型名、接口地址、代理地址、温度或 Token 上限。连接成功后，模型选择器自动出现该 Key 可以使用的获准模型。Key 加密保存，页面和接口永远只返回掩码；测试失败只返回“Key 无效 / 余额不足 / 网络不可用 / 暂不支持”四类可读错误，不回传供应商原始响应和密钥。

### 1.4 极简用户本地模型接入

纯 Web 云端无法直接、安全、稳定地调用用户电脑的 `127.0.0.1`。首期只支持 Ollama，并提供一个轻量的 `DSA Local Connector`：

- 它不是 DSA 桌面版，只负责连接和转发本地模型任务。
- 用户下载安装后双击运行；小窗口只显示“未连接 / 已连接 / Ollama 未启动 / 没有模型”。
- 连接器自动访问 `127.0.0.1:11434`，自动发现模型，不让用户填写地址、端口或模型名。
- 连接器只主动向 DSA 发起 HTTPS 请求，不开放公网端口。
- 浏览器生成一次性配对码；连接器领取短期设备令牌后保存到 Windows Credential Manager。
- 云端只保存设备令牌哈希、模型清单摘要和在线状态，不保存用户本地模型文件。
- 用户可以在账号页随时断开设备并使设备令牌失效。
- V107 的 `api_key_mode=local` 继续只代表 DSA 服务器自有 Ollama；用户电脑上的 Ollama 使用新的 `user_local` 来源，二者不得混用或互相回退。

## 2. 用户界面只保留一个入口

账号页新增“模型与 API”卡片，首页分析按钮旁新增一个紧凑的“当前模型”按钮。用户点击后只看到：

```text
选择模型

[ 平台模型 ]  推荐，直接使用
[ 我的 API ]  已连接 1 个 / 去连接
[ 本地模型 ]  已连接 / 去连接

当前：平台推荐
```

选择“我的 API”后：

```text
连接我的 API

1. 选择供应商： [OpenAI] [Claude] [DeepSeek]
2. 粘贴 API Key： [••••••••••••]
3.                 [连接并测试]
```

选择“本地模型”后：

```text
连接本地模型

1. [下载 DSA Local Connector]
2. 双击运行连接器
3. 配对码： 882 168   [复制]

状态：等待连接
```

额度耗尽时只显示一个操作弹层：

```text
本月 API 次数已用完

API 加油包  HK$28
168 Flash + 28 Pro
有效至：2026-08-12 14:30

[购买加油包]  [改用我的 API]
```

不新增独立“高级设置”页面；用户接入全部放在现有 `/account`，模型切换全部复用同一个选择器。

## 3. 当前基线与实施边界

- 现有 `src/platform_feature_policy.py` 仍是周额度桶，产品规则已经改为免费用户按周、付费会员按会员月；V112 必须增加付费额度 grant，不能继续把 PRO/MAX 写成周额度常量。
- 现有 `src/platform_accounts.py` 只识别 `free/pro/premium/enterprise`；V112 必须增加 `plus/pro/max` 产品等级并保留旧值读取兼容，不删除现有用户。
- 现有计费只处理订阅 plan；加油包必须作为 `add_on` 商品处理，支付完成不得把用户 plan 改成商品代码。
- V111 多供应商 BYOK 请求级路由是 V112-A 的前置条件。V111 未通过确定性门禁时，可以开发 UI 和模拟测试，但不得宣称 OpenAI/Claude/DeepSeek 已真实可用。
- 现有 V107 Ollama 是 DSA 服务器本地运行时，不是用户本机模型。本计划新增连接器，不修改 V107 的内部降级定位。
- 本计划不开放任意中转 Base URL；中转站只有经过管理员审核、加入平台模型目录后，才可以作为平台线路出现。
- 本计划不连接真实支付、不使用真实用户 Key、不执行真实供应商调用；这些都保留为受控人工验收门禁。
- 所有输出继续显示“仅供信息分析，不构成投资建议”，不新增买卖指令、目标价、仓位或收益承诺。
- 当前工作树已有大量 V106–V111 改动；实施时只暂存本计划明确列出的文件，不执行 `git add -A`、`git clean`、`git reset --hard` 或覆盖用户改动。

## 4. 文件职责图

### 4.1 新建文件

- `src/services/api_boost_pack_service.py`：加油包商品、购买资格、额度发放、余额与失效规则。
- `src/services/member_model_catalog_service.py`：统一输出平台、BYOK、用户本地三种模型选项并执行会员权限过滤。
- `src/services/user_local_connector_service.py`：配对、设备令牌、心跳、任务长轮询和结果回传。
- `api/v1/endpoints/local_connector.py`：用户本地连接器 API。
- `api/v1/schemas/local_connector.py`：连接器 API 契约。
- `apps/dsa-web/src/components/platform/BoostPackCardV112.tsx`：加油包余额和购买入口。
- `apps/dsa-web/src/components/platform/SimpleModelPickerV112.tsx`：三个来源的统一模型选择器。
- `apps/dsa-web/src/components/platform/ModelConnectionWizardV112.tsx`：三步 BYOK 和本地连接向导。
- `apps/dsa-local-connector/app.py`：Windows 小窗口和启动入口。
- `apps/dsa-local-connector/client.py`：配对、心跳和长轮询客户端。
- `apps/dsa-local-connector/ollama.py`：只允许访问回环地址的 Ollama 发现与调用。
- `apps/dsa-local-connector/requirements.txt`：连接器独立依赖。
- `apps/dsa-local-connector/dsa-local-connector.spec`：PyInstaller 打包配置。
- `tests/test_platform_boost_pack_v112.py`：加油包资格、幂等、失效和扣减测试。
- `tests/test_member_model_catalog_v112.py`：模型目录和会员过滤测试。
- `tests/test_analysis_model_selection_v112.py`：请求级模型选择和额度权重测试。
- `tests/test_user_local_connector_v112.py`：配对、令牌、长轮询、失效和越权测试。
- `apps/dsa-web/src/components/platform/__tests__/BoostPackCardV112.test.tsx`。
- `apps/dsa-web/src/components/platform/__tests__/SimpleModelPickerV112.test.tsx`。
- `apps/dsa-web/src/components/platform/__tests__/ModelConnectionWizardV112.test.tsx`。
- `scripts/verify_platform_simple_model_access_v112.py`：确定性验收器，成功输出 `DSA_PLATFORM_SIMPLE_MODEL_ACCESS_V112_OK`。
- `tests/test_platform_simple_model_access_v112_verifier.py`：验收器回归测试。

### 4.2 修改文件

- `src/storage.py`：增加付费额度 grant、额度 reservation、本地连接器和本地任务表；为订阅和 checkout 增加周期/商品字段。
- `src/platform_accounts.py`：增加 PLUS/PRO/MAX 兼容映射和付费额度查询入口。
- `src/platform_feature_policy.py`：免费周额度和付费会员月额度分离；BYOK/本地只消耗服务器公平使用桶。
- `src/billing/payment_provider.py`：支持订阅和 `add_on` 两类 checkout 商品。
- `src/billing/lifecycle.py`：加油包支付成功时幂等发放额度，不改变订阅 plan。
- `api/v1/schemas/billing.py`、`api/v1/endpoints/billing.py`：新增加油包 checkout 和余额响应。
- `api/v1/schemas/platform.py`、`api/v1/endpoints/platform.py`：新增模型选项、连接并测试 Key、连接器状态接口。
- `api/v1/schemas/analysis.py`、`api/v1/endpoints/analysis.py`：接受单一 `model_option_id` 并在扣额度前解析。
- `src/services/analysis_service.py`、`src/services/task_queue.py`：把已解析模型选择贯通同步/异步链。
- `api/v1/endpoints/__init__.py`、`api/v1/router.py`：注册本地连接器路由。
- `.env.example`：增加三个功能开关和连接器 TTL；模型目录继续复用现有运行时部署与 V111 白名单。
- `apps/dsa-web/src/api/platform.ts`、`apps/dsa-web/src/api/analysis.ts`：增加加油包、模型目录、Key 连接测试和连接器 API。
- `apps/dsa-web/src/pages/AccountPage.tsx`：用向导替换手写供应商/模型字段，加入加油包和本地连接器卡片。
- `apps/dsa-web/src/pages/HomePage.tsx`：加入紧凑模型选择器和额度耗尽弹层。
- `apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx`、`apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`。
- `scripts/verify_platform_release_candidate_package.py`、`tests/test_platform_release_candidate_package.py`。
- `docs/superpowers/platform-product-rules.md`、`docs/superpowers/platform-local-v1-acceptance-status.md`、`docs/superpowers/platform-release-candidate-manifest.md`、`docs/superpowers/platform-review-slices.md`、`docs/CHANGELOG.md`。

### 4.3 明确不修改

- 不把用户本地模型塞进 `src/services/ollama_runtime_service.py`；该文件继续只负责 DSA 服务器 V107 Ollama。
- 不新增桌面版页面，不修改 `apps/dsa-desktop/`。
- 不在用户页面暴露 `apps/dsa-web/src/components/settings/LLMChannelEditor.tsx` 的管理员通道配置。
- 不允许用户输入任意 Base URL。
- 不删除旧额度流水、旧密钥或旧订阅记录。

## 5. 实施顺序

V112-A 必须先完成 Task 1–5，交付加油包、模型选择和极简 BYOK。V112-B 再完成 Task 6–7，交付用户本地 Ollama。Task 8 统一验收。

### Task 1: 建立会员月额度和加油包数据契约

**Files:**
- Modify: `src/storage.py`
- Modify: `src/platform_accounts.py`
- Modify: `src/platform_feature_policy.py`
- Test: `tests/test_platform_boost_pack_v112.py`

- [ ] **Step 1: 写失败测试，固定产品等级和额度表**

```python
def test_v112_membership_quota_contract():
    assert normalize_membership_plan("premium") == "max"
    assert normalize_membership_plan("plus") == "plus"
    assert membership_month_quota("pro") == {"flash": 268, "pro": 28}
    assert membership_month_quota("max") == {"flash": 1688, "pro": 168}
    assert membership_month_quota("plus") == {"flash": 0, "pro": 0}
```

- [ ] **Step 2: 写失败测试，固定 additive 表和失效字段**

```python
def test_quota_grant_has_separate_flash_pro_and_expiry(db):
    grant = PlatformQuotaGrant(
        user_id=1,
        source_type="boost_pack",
        source_reference="evt_paid_1",
        flash_total=168,
        flash_used=0,
        pro_total=28,
        pro_used=0,
        starts_at=datetime(2026, 7, 12, 10, 0),
        expires_at=datetime(2026, 8, 12, 10, 0),
        status="active",
    )
    db.add(grant)
    db.commit()
    assert grant.flash_total == 168
    assert grant.pro_total == 28
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/test_platform_boost_pack_v112.py -q
```

Expected: FAIL，提示 `normalize_membership_plan` 或 `PlatformQuotaGrant` 尚不存在。

- [ ] **Step 4: 增加最小数据模型**

在 `src/storage.py` 增加：

```python
class PlatformQuotaGrant(Base):
    __tablename__ = "platform_quota_grants"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("platform_users.id"), nullable=False, index=True)
    source_type = Column(String(32), nullable=False, index=True)
    source_reference = Column(String(128), nullable=False, unique=True, index=True)
    flash_total = Column(Integer, nullable=False, default=0)
    flash_used = Column(Integer, nullable=False, default=0)
    pro_total = Column(Integer, nullable=False, default=0)
    pro_used = Column(Integer, nullable=False, default=0)
    starts_at = Column(DateTime, nullable=False, index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    status = Column(String(32), nullable=False, default="active", index=True)
    created_at = Column(DateTime, default=utc_naive_now, nullable=False, index=True)


class PlatformQuotaReservation(Base):
    __tablename__ = "platform_quota_reservations"

    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("platform_users.id"), nullable=False, index=True)
    reference_id = Column(String(128), nullable=False, unique=True, index=True)
    quota_type = Column(String(16), nullable=False, index=True)
    units = Column(Integer, nullable=False)
    allocations_json = Column(Text, nullable=False, default="[]")
    status = Column(String(16), nullable=False, default="reserved", index=True)
    created_at = Column(DateTime, default=utc_naive_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_naive_now, onupdate=utc_naive_now)
```

为 `PlatformBillingSubscription` 增加 `current_period_start`、`current_period_end`、`expires_at`；为 `PlatformBillingCheckoutSession` 增加 `product_type` 和 `product_code`。在初始化阶段增加 `_ensure_platform_billing_v112_columns()`，只做 additive SQLite 列补齐，不删除和重建表。旧订阅没有周期字段时不猜测失效时间，也不开放加油包；下一次订阅更新事件必须写入完整周期后才可购买。

- [ ] **Step 5: 增加会员等级兼容和产品额度常量**

```python
MEMBERSHIP_MONTH_QUOTAS = {
    "plus": {"flash": 0, "pro": 0},
    "pro": {"flash": 268, "pro": 28},
    "max": {"flash": 1688, "pro": 168},
}

LEGACY_PLAN_ALIASES = {
    "premium": "max",
}


def normalize_membership_plan(plan: str) -> str:
    normalized = (plan or "free").strip().lower()
    return LEGACY_PLAN_ALIASES.get(normalized, normalized)
```

`enterprise` 保留给管理员/企业兼容，不在消费者购买页显示，也不自动迁移为 MAX。

- [ ] **Step 6: 运行测试并确认通过**

Run:

```powershell
python -m pytest tests/test_platform_boost_pack_v112.py -q
python -m pytest tests/test_platform_ai_feature_quota.py tests/test_billing_subscription_lifecycle.py -q
```

Expected: PASS；旧表数据仍能读取，旧测试不回归。

- [ ] **Step 7: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add src/storage.py src/platform_accounts.py src/platform_feature_policy.py tests/test_platform_boost_pack_v112.py
git commit -m "feat: add monthly quota grant contract"
```

### Task 2: 把加油包接入现有计费生命周期

**Files:**
- Create: `src/services/api_boost_pack_service.py`
- Modify: `src/billing/payment_provider.py`
- Modify: `src/billing/lifecycle.py`
- Modify: `api/v1/schemas/billing.py`
- Modify: `api/v1/endpoints/billing.py`
- Test: `tests/test_platform_boost_pack_v112.py`

- [ ] **Step 1: 写失败测试，证明 add-on 不会修改会员 plan**

```python
def test_completed_boost_pack_checkout_grants_quota_without_changing_plan(client, pro_user):
    checkout = client.post(
        "/api/v1/billing/boost-pack/checkout",
        json={"product_code": "api_boost_168_28"},
    )
    assert checkout.status_code == 200

    completed = send_signed_checkout_completed(checkout.json()["provider_session_id"])
    assert completed.status_code == 200
    assert account_for(pro_user.id).plan == "pro"
    assert boost_balance(pro_user.id) == {"flash": 168, "pro": 28}
```

- [ ] **Step 2: 写失败测试，覆盖资格、临近到期和 webhook 幂等**

```python
def test_boost_pack_requires_active_pro_or_max(client, plus_user):
    response = client.post(
        "/api/v1/billing/boost-pack/checkout",
        json={"product_code": "api_boost_168_28"},
    )
    assert response.status_code == 403
    assert response.json()["error"] == "boost_pack_not_available"


def test_duplicate_payment_event_grants_only_once(client, pro_user):
    event = completed_boost_event("evt_boost_same")
    first = post_signed_event(client, event)
    second = post_signed_event(client, event)
    assert first.status_code == 200
    assert second.status_code == 200
    assert count_grants("evt_boost_same") == 1
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/test_platform_boost_pack_v112.py -q
```

Expected: FAIL，提示加油包 endpoint 或 service 不存在。

- [ ] **Step 4: 实现固定商品和购买资格**

```python
@dataclass(frozen=True)
class BoostPackProduct:
    code: str = "api_boost_168_28"
    price_hkd: int = 28
    flash_units: int = 168
    pro_units: int = 28


class ApiBoostPackService:
    PRODUCT = BoostPackProduct()
    MIN_REMAINING_MINUTES = 60

    def assert_can_purchase(self, *, user_id: int, now: datetime) -> PlatformBillingSubscription:
        subscription = self._active_subscription(user_id)
        if normalize_membership_plan(subscription.plan) not in {"pro", "max"}:
            raise BoostPackNotAvailable("boost_pack_not_available")
        expires_at = min(subscription.current_period_end, subscription.expires_at)
        if expires_at <= now + timedelta(minutes=self.MIN_REMAINING_MINUTES):
            raise BoostPackNotAvailable("renew_membership_first")
        return subscription
```

- [ ] **Step 5: 区分 subscription 和 add_on checkout**

`CheckoutSession`、checkout 表和 webhook payload 必须携带：

```python
{
    "product_type": "add_on",
    "product_code": "api_boost_168_28",
    "amount": 28,
    "currency": "HKD",
}
```

`BillingLifecycleService._process_checkout_event()` 遇到 `product_type == "add_on"` 时调用 `ApiBoostPackService.grant_from_payment_event()`；遇到订阅时保持原逻辑。两条分支都使用 `provider_event_id` 幂等，但 add-on 分支严禁调用 `_set_user_plan()`。

- [ ] **Step 6: 暴露极简 checkout 和余额接口**

```python
class BoostPackCheckoutRequest(BaseModel):
    product_code: Literal["api_boost_168_28"]


@router.post("/boost-pack/checkout")
async def create_boost_pack_checkout(request: Request, body: BoostPackCheckoutRequest):
    user_id = _require_platform_user(request)
    service = ApiBoostPackService()
    service.assert_can_purchase(user_id=user_id, now=utc_naive_now())
    return service.create_checkout(user_id=user_id, product_code=body.product_code)
```

账号接口返回 `boost_pack`：商品价格、Flash/Pro 数量、当前加油包余额、准确失效时间和 `can_purchase`。

- [ ] **Step 7: 运行计费回归**

Run:

```powershell
python -m pytest tests/test_platform_boost_pack_v112.py tests/test_billing_api.py tests/test_billing_sandbox_flow.py tests/test_billing_subscription_lifecycle.py -q
python scripts/verify_platform_billing_lifecycle.py
```

Expected: PASS，并输出 `DSA_PLATFORM_BILLING_LIFECYCLE_V1_OK`。

- [ ] **Step 8: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add src/services/api_boost_pack_service.py src/billing/payment_provider.py src/billing/lifecycle.py api/v1/schemas/billing.py api/v1/endpoints/billing.py tests/test_platform_boost_pack_v112.py
git commit -m "feat: sell idempotent API boost packs"
```

### Task 3: 在分析主链正确扣减会员月额度

**Files:**
- Modify: `src/services/api_boost_pack_service.py`
- Modify: `src/platform_accounts.py`
- Modify: `api/v1/endpoints/analysis.py`
- Modify: `src/services/analysis_service.py`
- Modify: `src/services/task_queue.py`
- Test: `tests/test_platform_boost_pack_v112.py`
- Test: `tests/test_analysis_model_selection_v112.py`

- [ ] **Step 1: 写失败测试，固定扣减顺序和原子性**

```python
def test_member_grant_is_spent_before_boost_grant(quota_service, pro_user):
    base = create_grant(pro_user.id, "membership", flash=1, pro=0, expires_in_days=10)
    boost = create_grant(pro_user.id, "boost_pack", flash=168, pro=28, expires_in_days=10)
    quota_service.reserve(pro_user.id, "flash", 2, "analysis:req-1")
    assert reload(base).flash_used == 1
    assert reload(boost).flash_used == 1


def test_insufficient_combined_balance_does_not_partially_debit(quota_service, pro_user):
    grant = create_grant(pro_user.id, "membership", flash=1, pro=0, expires_in_days=10)
    with pytest.raises(QuotaExceeded):
        quota_service.reserve(pro_user.id, "flash", 2, "analysis:req-2")
    assert reload(grant).flash_used == 0
```

- [ ] **Step 2: 写失败测试，证明 release 幂等**

```python
def test_failed_analysis_releases_same_reservation_once(quota_service, pro_user):
    create_grant(pro_user.id, "boost_pack", flash=168, pro=28, expires_in_days=10)
    quota_service.reserve(pro_user.id, "pro", 3, "analysis:req-3")
    quota_service.release("analysis:req-3")
    quota_service.release("analysis:req-3")
    assert quota_service.balance(pro_user.id)["pro"] == 28
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/test_platform_boost_pack_v112.py tests/test_analysis_model_selection_v112.py -q
```

Expected: FAIL，当前周额度桶不能表达会员月 grant。

- [ ] **Step 4: 实现 grant reservation**

`reserve()` 在一个写事务中完成：

1. 过滤 `status=active`、`starts_at <= now < expires_at` 的 grant。
2. 按 `membership` 在前、`boost_pack` 在后，再按最早失效排序。
3. 计算完整 allocations；余额不足直接回滚。
4. 增加各 grant 的 used 值并写入唯一 `reference_id` reservation。
5. 重复 reference 返回原 reservation，不重复扣减。

`release()` 读取 `allocations_json`，只允许 `reserved -> released` 一次；成功分析把状态改为 `consumed`。

- [ ] **Step 5: 在模型解析后、任务提交前扣额度**

平台模型必须先解析出 `quota_type` 和 `cost_units`，再扣对应 Flash/Pro。BYOK 和 `user_local` 不扣平台模型 grant，但继续调用现有服务器公平使用桶；预检失败不得扣任何额度。

- [ ] **Step 6: 返回稳定的额度耗尽响应**

```json
{
  "error": "member_api_quota_exhausted",
  "quota_type": "pro",
  "boost_pack": {
    "available": true,
    "price_hkd": 28,
    "flash": 168,
    "pro": 28,
    "expires_at": "2026-08-12T14:30:00"
  }
}
```

- [ ] **Step 7: 运行同步、异步和失败释放回归**

Run:

```powershell
python -m pytest tests/test_platform_boost_pack_v112.py tests/test_analysis_model_selection_v112.py tests/test_platform_ai_feature_quota.py tests/test_analysis_api_contract.py -q
```

Expected: PASS；同步和异步使用相同 reservation 语义。

- [ ] **Step 8: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add src/services/api_boost_pack_service.py src/platform_accounts.py api/v1/endpoints/analysis.py src/services/analysis_service.py src/services/task_queue.py tests/test_platform_boost_pack_v112.py tests/test_analysis_model_selection_v112.py
git commit -m "feat: consume monthly member API grants"
```

### Task 4: 建立统一、可过滤的会员模型目录

**Files:**
- Create: `src/services/member_model_catalog_service.py`
- Modify: `.env.example`
- Modify: `api/v1/schemas/platform.py`
- Modify: `api/v1/endpoints/platform.py`
- Modify: `api/v1/schemas/analysis.py`
- Modify: `api/v1/endpoints/analysis.py`
- Test: `tests/test_member_model_catalog_v112.py`
- Test: `tests/test_analysis_model_selection_v112.py`
- Test: `tests/test_platform_api_keys_product.py`

- [ ] **Step 1: 写失败测试，固定不同会员看到的模型**

```python
def test_catalog_filters_options_by_member_plan(catalog):
    assert ids(catalog.list_options(plan="free")) == ["platform_recommended"]
    assert "platform_pro" not in ids(catalog.list_options(plan="plus"))
    assert "platform_pro" in ids(catalog.list_options(plan="pro"))
    assert "platform_flagship" in ids(catalog.list_options(plan="max"))
```

- [ ] **Step 2: 写失败测试，固定客户端只发送一个 option ID**

```python
def test_resolve_option_rechecks_key_ownership(catalog, pro_user, other_user_key):
    with pytest.raises(ModelOptionNotAvailable):
        catalog.resolve(
            user_id=pro_user.id,
            model_option_id=f"byok:{other_user_key.id}:recommended",
        )
```

```python
def test_connect_api_key_returns_mask_and_options_without_plaintext(client, plus_user):
    response = client.post(
        "/api/v1/platform/api-keys/connect",
        json={"provider": "openai", "api_key": "sk-test-connect"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["api_key"]["masked_key"]
    assert "sk-test-connect" not in str(body)
    assert body["model_options"]
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/test_member_model_catalog_v112.py tests/test_analysis_model_selection_v112.py -q
```

Expected: FAIL，统一模型目录尚不存在。

- [ ] **Step 4: 实现服务端模型选项 DTO**

```python
@dataclass(frozen=True)
class MemberModelOption:
    option_id: str
    label_zh: str
    label_en: str
    source: str
    provider_label: str
    speed: str
    purpose: str
    quota_type: str | None
    cost_units: int
    recommended: bool
```

目录从现有运行时部署和 V111 BYOK 白名单构建；内部模型名、Base URL 和密钥不进入响应。平台目录由管理员配置，空目录时 fail closed，只返回可验证的默认选项。

- [ ] **Step 5: 增加单一模型选择接口**

```python
@router.get("/model-options", response_model=PlatformModelOptionsResponse)
async def platform_model_options(request: Request):
    identity = _require_platform_identity(request)
    return MemberModelCatalogService().list_for_user(identity.user_id)
```

增加 `POST /api/v1/platform/api-keys/connect`。请求只接受 `provider` 和 `api_key`；provider 固定为 `openai`、`anthropic`、`deepseek`。服务端使用 V111 白名单中的低成本探测模型执行一次受限测试，成功后加密保存并返回掩码和刷新后的模型选项；失败时不落库。响应错误只允许：`invalid_api_key`、`provider_balance_insufficient`、`provider_unreachable`、`provider_not_supported`。测试调用可能产生极少量供应商费用，按钮旁必须提前说明。

`AnalyzeRequest` 增加：

```python
model_option_id: str = Field("platform_recommended", min_length=3, max_length=160)
```

前端不再组合 provider/model/base URL；服务端把 option ID 解析为 V111 的请求级选择。旧 V111 字段只作为内部兼容输入保留，不在普通用户 UI 暴露。

- [ ] **Step 6: 加入三个功能开关**

```dotenv
PLATFORM_BOOST_PACK_ENABLED=false
PLATFORM_MEMBER_MODEL_PICKER_ENABLED=false
PLATFORM_USER_LOCAL_CONNECTOR_ENABLED=false
```

开关关闭时保持旧行为：平台推荐模型、无加油包按钮、无用户本地连接入口。

- [ ] **Step 7: 运行目录和分析契约测试**

Run:

```powershell
python -m pytest tests/test_member_model_catalog_v112.py tests/test_analysis_model_selection_v112.py tests/test_platform_api_keys_product.py tests/test_platform_byok_routing_v111.py tests/test_analysis_api_contract.py -q
```

Expected: PASS；未完成 V111 时保持 `REAL_OPENAI_CLAUDE_BYOK_NOT_VERIFIED`，不伪造真实验收。

- [ ] **Step 8: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add src/services/member_model_catalog_service.py .env.example api/v1/schemas/platform.py api/v1/endpoints/platform.py api/v1/schemas/analysis.py api/v1/endpoints/analysis.py tests/test_member_model_catalog_v112.py tests/test_analysis_model_selection_v112.py tests/test_platform_api_keys_product.py
git commit -m "feat: expose simple member model options"
```

### Task 5: 把 Web 接入压缩为三步

**Files:**
- Create: `apps/dsa-web/src/components/platform/BoostPackCardV112.tsx`
- Create: `apps/dsa-web/src/components/platform/SimpleModelPickerV112.tsx`
- Create: `apps/dsa-web/src/components/platform/ModelConnectionWizardV112.tsx`
- Create: `apps/dsa-web/src/components/platform/__tests__/BoostPackCardV112.test.tsx`
- Create: `apps/dsa-web/src/components/platform/__tests__/SimpleModelPickerV112.test.tsx`
- Create: `apps/dsa-web/src/components/platform/__tests__/ModelConnectionWizardV112.test.tsx`
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `apps/dsa-web/src/api/analysis.ts`
- Modify: `apps/dsa-web/src/pages/AccountPage.tsx`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: 写失败测试，证明默认用户不需要配置**

```tsx
it('defaults to platform recommended and hides technical fields', async () => {
  render(<SimpleModelPickerV112 options={options} value="platform_recommended" onChange={vi.fn()} />);
  expect(screen.getByText('平台推荐')).toBeInTheDocument();
  expect(screen.queryByLabelText(/Base URL/i)).not.toBeInTheDocument();
  expect(screen.queryByLabelText(/模型内部名称/i)).not.toBeInTheDocument();
});
```

- [ ] **Step 2: 写失败测试，证明 BYOK 只有三步**

```tsx
it('connects a provider with provider, key and one action', async () => {
  render(<ModelConnectionWizardV112 mode="byok" />);
  await user.click(screen.getByRole('button', { name: 'OpenAI' }));
  await user.type(screen.getByLabelText('API Key'), 'sk-test-value');
  await user.click(screen.getByRole('button', { name: '连接并测试' }));
  expect(platformApi.connectApiKey).toHaveBeenCalledWith({ provider: 'openai', apiKey: 'sk-test-value' });
});
```

- [ ] **Step 3: 写失败测试，固定额度耗尽弹层**

```tsx
it('offers boost pack or BYOK when member quota is exhausted', async () => {
  render(<HomePage />);
  await emitAnalysisError({ error: 'member_api_quota_exhausted', boostPack: boostPack });
  expect(screen.getByText('HK$28')).toBeInTheDocument();
  expect(screen.getByText('168 Flash + 28 Pro')).toBeInTheDocument();
  expect(screen.getByRole('button', { name: '购买加油包' })).toBeEnabled();
  expect(screen.getByRole('button', { name: '改用我的 API' })).toBeEnabled();
});
```

- [ ] **Step 4: 运行前端测试并确认失败**

Run:

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/platform src/pages/__tests__/AccountPage.test.tsx src/pages/__tests__/HomePage.test.tsx
```

Expected: FAIL，三个 V112 组件尚不存在。

- [ ] **Step 5: 实现统一模型选择器**

组件只接收：

```ts
export type SimpleModelOption = {
  optionId: string;
  label: string;
  source: 'platform' | 'byok' | 'user_local';
  providerLabel: string;
  speed: 'fast' | 'balanced' | 'strong';
  purpose: string;
  quotaType: 'flash' | 'pro' | null;
  costUnits: number;
  recommended: boolean;
};
```

首页 localStorage 只保存 `modelOptionId`；每次加载都以服务端返回目录复核。失效选项清除并回到 `platform_recommended`，同时显示一次非阻断提示。

- [ ] **Step 6: 用供应商卡片替换手写模型输入框**

`AccountPage.tsx` 删除普通用户可见的 model 文本输入。`connectApiKey()` 只发送 provider 和 Key；成功后清空输入并重新获取模型目录。Key 输入使用 `type=password`、`autoComplete=off`，任何 React state、toast 和测试快照都不得保留 Key 值。

- [ ] **Step 7: 实现加油包购买卡**

只有 `canPurchase=true` 时显示主按钮。卡片必须显示价格、两类次数、准确失效时间和“不退款、不结转”。checkout 创建后跳转现有支付 URL；返回账号页后轮询 billing account，直到 grant 出现或 30 秒超时并给出可重试提示。

- [ ] **Step 8: 运行前端测试、lint 和 build**

Run:

```powershell
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/platform src/pages/__tests__/AccountPage.test.tsx src/pages/__tests__/HomePage.test.tsx src/api/__tests__/platform.test.ts src/api/__tests__/analysis.test.ts
npm run lint
npm run build
```

Expected: 全部 PASS，build 成功。

- [ ] **Step 9: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add apps/dsa-web/src/components/platform apps/dsa-web/src/api/platform.ts apps/dsa-web/src/api/analysis.ts apps/dsa-web/src/pages/AccountPage.tsx apps/dsa-web/src/pages/HomePage.tsx apps/dsa-web/src/pages/__tests__/AccountPage.test.tsx apps/dsa-web/src/pages/__tests__/HomePage.test.tsx
git commit -m "feat: simplify model and boost pack setup"
```

### Task 6: 建立用户本地连接器后端

**Files:**
- Create: `src/services/user_local_connector_service.py`
- Create: `api/v1/endpoints/local_connector.py`
- Create: `api/v1/schemas/local_connector.py`
- Modify: `.env.example`
- Modify: `src/storage.py`
- Modify: `api/v1/endpoints/__init__.py`
- Modify: `api/v1/router.py`
- Modify: `src/services/member_model_catalog_service.py`
- Modify: `api/v1/endpoints/analysis.py`
- Modify: `src/services/analysis_service.py`
- Test: `tests/test_user_local_connector_v112.py`
- Test: `tests/test_analysis_model_selection_v112.py`

- [ ] **Step 1: 写失败测试，固定一次性配对和令牌哈希**

```python
def test_pairing_code_is_single_use_and_device_token_is_not_stored_plaintext(service, plus_user):
    pairing = service.create_pairing(user_id=plus_user.id)
    claimed = service.claim_pairing(pairing.code, device_name="My PC")
    assert claimed.device_token
    assert service.claim_pairing(pairing.code, device_name="Other PC").error == "pairing_code_used"
    row = load_connector(claimed.connector_id)
    assert row.device_token_hash != claimed.device_token
    assert claimed.device_token not in row.device_token_hash
```

- [ ] **Step 2: 写失败测试，覆盖跨用户和任务过期**

```python
def test_connector_cannot_claim_another_users_job(service, user_a, user_b):
    connector_a = paired_connector(user_a.id)
    job_b = create_local_job(user_b.id)
    assert service.complete_job(connector_a.token, job_b.id, "result").error == "job_not_found"


def test_expired_local_job_is_not_delivered(service, connector):
    create_local_job(connector.user_id, expires_at=utc_now() - timedelta(seconds=1))
    assert service.next_job(connector.token, wait_seconds=0) is None
```

- [ ] **Step 3: 运行测试并确认失败**

Run:

```powershell
python -m pytest tests/test_user_local_connector_v112.py tests/test_analysis_model_selection_v112.py -q
```

Expected: FAIL，本地连接器 service 和表尚不存在。

- [ ] **Step 4: 增加最小持久化表**

```python
class PlatformLocalConnector(Base):
    __tablename__ = "platform_local_connectors"
    id = Column(Integer, primary_key=True, autoincrement=True)
    user_id = Column(Integer, ForeignKey("platform_users.id"), nullable=False, index=True)
    device_name = Column(String(128), nullable=False)
    device_token_hash = Column(String(128), nullable=False, unique=True, index=True)
    models_json = Column(Text, nullable=False, default="[]")
    status = Column(String(16), nullable=False, default="offline", index=True)
    last_seen_at = Column(DateTime, index=True)
    revoked_at = Column(DateTime, index=True)
    created_at = Column(DateTime, default=utc_naive_now, nullable=False, index=True)


class PlatformLocalModelJob(Base):
    __tablename__ = "platform_local_model_jobs"
    id = Column(String(64), primary_key=True)
    user_id = Column(Integer, ForeignKey("platform_users.id"), nullable=False, index=True)
    connector_id = Column(Integer, ForeignKey("platform_local_connectors.id"), nullable=False, index=True)
    model_name = Column(String(160), nullable=False)
    request_ciphertext = Column(Text, nullable=False)
    response_ciphertext = Column(Text)
    status = Column(String(16), nullable=False, default="queued", index=True)
    expires_at = Column(DateTime, nullable=False, index=True)
    created_at = Column(DateTime, default=utc_naive_now, nullable=False, index=True)
    updated_at = Column(DateTime, default=utc_naive_now, onupdate=utc_naive_now)
```

一次性配对码不持久化明文；只保存带 TTL 的哈希。设备 token 使用至少 256 bit 随机值，数据库只保存 SHA-256/HMAC 哈希。任务请求和结果使用平台密钥加密后写入 `request_ciphertext` / `response_ciphertext`，完成任务的明文不得写日志；任务消费完成 24 小时后清空两列密文，只保留状态、耗时和审计字段。

- [ ] **Step 5: 实现出站 HTTPS 长轮询接口**

用户登录接口：

- `POST /api/v1/platform/local-connectors/pairing-code`
- `GET /api/v1/platform/local-connectors`
- `DELETE /api/v1/platform/local-connectors/{connector_id}`

设备 Bearer token 接口：

- `POST /api/v1/local-connector/claim`
- `POST /api/v1/local-connector/heartbeat`
- `GET /api/v1/local-connector/jobs/next?wait_seconds=25`
- `POST /api/v1/local-connector/jobs/{job_id}/complete`

长轮询最多 25 秒；设备离线 90 秒后从模型目录隐藏。撤销设备后所有请求立即返回 401。

`.env.example` 增加：

```dotenv
PLATFORM_LOCAL_CONNECTOR_PAIRING_TTL_SECONDS=300
PLATFORM_LOCAL_CONNECTOR_OFFLINE_SECONDS=90
PLATFORM_LOCAL_JOB_TTL_SECONDS=120
```

- [ ] **Step 6: 把 `user_local` 接入分析主链**

服务端只把经过分析模板生成的请求发给当前用户自己的 connector。任务响应只允许 JSON 文本结果和受限诊断；连接器不得请求任意服务器文件或执行任意命令。用户本地模型失败时不得回退到平台 API 或 BYOK。

- [ ] **Step 7: 运行安全和路由回归**

Run:

```powershell
python -m pytest tests/test_user_local_connector_v112.py tests/test_analysis_model_selection_v112.py tests/test_platform_ollama_analysis_v107.py tests/test_platform_byok_routing_v111.py -q
```

Expected: PASS；`local` 与 `user_local` 互不回退。

- [ ] **Step 8: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add src/services/user_local_connector_service.py api/v1/endpoints/local_connector.py api/v1/schemas/local_connector.py .env.example src/storage.py api/v1/endpoints/__init__.py api/v1/router.py src/services/member_model_catalog_service.py api/v1/endpoints/analysis.py src/services/analysis_service.py tests/test_user_local_connector_v112.py tests/test_analysis_model_selection_v112.py
git commit -m "feat: add user-owned Ollama connector backend"
```

### Task 7: 交付一键式 Windows 本地连接器

**Files:**
- Create: `apps/dsa-local-connector/app.py`
- Create: `apps/dsa-local-connector/client.py`
- Create: `apps/dsa-local-connector/ollama.py`
- Create: `apps/dsa-local-connector/requirements.txt`
- Create: `apps/dsa-local-connector/dsa-local-connector.spec`
- Modify: `apps/dsa-web/src/components/platform/ModelConnectionWizardV112.tsx`
- Modify: `apps/dsa-web/src/components/platform/__tests__/ModelConnectionWizardV112.test.tsx`
- Test: `tests/test_user_local_connector_v112.py`

- [ ] **Step 1: 写失败测试，禁止非回环 Ollama 地址**

```python
def test_ollama_client_only_accepts_loopback():
    assert OllamaClient("http://127.0.0.1:11434").base_url == "http://127.0.0.1:11434"
    with pytest.raises(ValueError):
        OllamaClient("http://192.168.1.20:11434")
    with pytest.raises(ValueError):
        OllamaClient("https://example.com")
```

- [ ] **Step 2: 写失败测试，证明模型自动发现且不自动下载**

```python
def test_discover_models_reads_tags_without_pulling(monkeypatch):
    calls = fake_ollama(monkeypatch, tags=["model-a", "model-b"])
    assert OllamaClient().discover_models() == ["model-a", "model-b"]
    assert all("/api/pull" not in call for call in calls)
```

- [ ] **Step 3: 实现只有四种状态的小窗口**

Tkinter 窗口只显示：

- `未连接：请在网页获取配对码`
- `正在连接 DSA`
- `已连接：发现 N 个 Ollama 模型`
- `Ollama 未启动或没有模型`

窗口只有“打开 DSA 账号页”“重新连接”“退出”三个按钮，不提供地址、端口、模型参数或高级设置。

- [ ] **Step 4: 实现令牌安全保存和长轮询**

设备 token 使用 `keyring` 保存到 Windows Credential Manager；日志只记录 connector ID、状态码和耗时，不记录 token、prompt、模型输出或用户数据。长轮询失败使用 1、2、5、10、30 秒上限退避，恢复后立即重新 heartbeat。

- [ ] **Step 5: 打包为单文件 exe**

`requirements.txt` 固定包含：

```text
keyring>=25,<26
pyinstaller>=6,<7
```

Run:

```powershell
Set-Location E:\DSA项目\apps\dsa-local-connector
python -m pip install -r requirements.txt
pyinstaller dsa-local-connector.spec --clean --noconfirm
```

Expected: 生成 `dist/DSA-Local-Connector.exe`；构建产物不提交仓库，只作为发布 artifact。

- [ ] **Step 6: 完成 Web 配对状态**

账号页点击“连接本地模型”后生成 6 位配对码并显示 5 分钟倒计时。连接成功后自动刷新模型目录；断开设备需要确认，但不删除历史分析。中英文文案都说明“这是轻量连接器，不是 DSA 桌面版”。

- [ ] **Step 7: 运行连接器和前端测试**

Run:

```powershell
Set-Location E:\DSA项目
python -m pytest tests/test_user_local_connector_v112.py -q
Set-Location E:\DSA项目\apps\dsa-web
npm test -- src/components/platform/__tests__/ModelConnectionWizardV112.test.tsx src/pages/__tests__/AccountPage.test.tsx
npm run build
```

Expected: PASS；前端构建成功。

- [ ] **Step 8: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add apps/dsa-local-connector apps/dsa-web/src/components/platform/ModelConnectionWizardV112.tsx apps/dsa-web/src/components/platform/__tests__/ModelConnectionWizardV112.test.tsx tests/test_user_local_connector_v112.py
git commit -m "feat: add one-click Ollama connector"
```

### Task 8: 验收器、文档、浏览器验收和回滚门禁

**Files:**
- Create: `scripts/verify_platform_simple_model_access_v112.py`
- Create: `tests/test_platform_simple_model_access_v112_verifier.py`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 写失败的验收器测试**

```python
def test_v112_verifier_prints_success_marker():
    result = subprocess.run(
        [sys.executable, "scripts/verify_platform_simple_model_access_v112.py"],
        cwd=PROJECT_ROOT,
        text=True,
        capture_output=True,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "DSA_PLATFORM_SIMPLE_MODEL_ACCESS_V112_OK" in result.stdout
```

- [ ] **Step 2: 运行并确认失败**

Run:

```powershell
python -m pytest tests/test_platform_simple_model_access_v112_verifier.py -q
```

Expected: FAIL，验收器尚不存在。

- [ ] **Step 3: 实现确定性验收器**

验收器顺序执行：

```python
BACKEND_TESTS = (
    "tests/test_platform_boost_pack_v112.py",
    "tests/test_member_model_catalog_v112.py",
    "tests/test_analysis_model_selection_v112.py",
    "tests/test_user_local_connector_v112.py",
    "tests/test_platform_byok_routing_v111.py",
    "tests/test_platform_ai_feature_quota.py",
    "tests/test_billing_subscription_lifecycle.py",
)

completed = subprocess.run(
    [sys.executable, "-m", "pytest", *BACKEND_TESTS, "-q"],
    cwd=REPO_ROOT,
    check=False,
)
if completed.returncode != 0:
    raise SystemExit(completed.returncode)
```

然后运行 Web 定向测试和 build。全部成功后打印：

```text
DSA_PLATFORM_SIMPLE_MODEL_ACCESS_V112_OK boost=168+28 price_hkd=28 sources=platform,byok,user_local secrets_exposed=false
```

- [ ] **Step 4: 同步产品、状态、manifest 和 changelog**

`docs/CHANGELOG.md` 的 `[Unreleased]` 使用扁平条目：

```markdown
- [新功能] 增加 HK$28 API 加油包和会员月额度流水
- [新功能] 增加平台、BYOK 和用户本地模型的统一简易选择器
- [改进] 将 API Key 接入简化为选择供应商、粘贴 Key、连接并测试
- [安全] 用户本地 Ollama 通过出站连接器接入且不开放公网端口
```

- [ ] **Step 5: 运行完整确定性门禁**

Run:

```powershell
Set-Location E:\DSA项目
python scripts/verify_platform_simple_model_access_v112.py
python scripts/verify_platform_release_candidate_package.py
python -m pytest -m "not network" -q
Set-Location E:\DSA项目\apps\dsa-web
npm run lint
npm run build
```

Expected: V112 marker、release candidate marker、pytest、lint 和 build 全部成功。

- [ ] **Step 6: 浏览器多角色、多市场和双语验收**

使用假支付、假 Key provider 和假本地 connector 覆盖：

- 角色：游客、普通客户、PLUS、PRO、MAX、管理员。
- 市场：A 股、港股、美股各一次查询和一次分析。
- 语言：中文、英文。
- 加油包：无资格、可购买、支付完成、重复 webhook、额度耗尽、会员月结束、会员到期。
- 模型：平台推荐、PRO 目录、MAX 目录、BYOK、用户本地、模型下线回到推荐。
- API：连接成功、Key 无效、余额不足、网络不可用、禁用、删除、无明文泄漏。
- 本地模型：未安装连接器、Ollama 未启动、无模型、连接成功、设备离线、设备撤销、任务超时。
- 页面必须显示准确额度、准确失效时间、数据发送说明和“仅供信息分析，不构成投资建议”。

验收截图放在 PR 描述或 Actions artifact，不提交仓库。未完成真实 OpenAI/Claude/DeepSeek 和真实用户 Ollama 验收时，状态必须分别保持：

```text
REAL_OPENAI_CLAUDE_BYOK_NOT_VERIFIED
REAL_USER_OLLAMA_CONNECTOR_NOT_VERIFIED
```

- [ ] **Step 7: 密钥和日志泄漏扫描**

Run:

```powershell
rg -n "sk-[A-Za-z0-9_-]{16,}|api[_-]?key[=:][^* ]+|device_token[=:][^* ]+" E:\DSA项目\logs E:\DSA项目\reports E:\DSA项目\docs E:\DSA项目\tests
```

Expected: 不出现真实密钥或设备 token；测试假值必须明显带 `test`/`fake` 且不能匹配生产密钥格式。

- [ ] **Step 8: 条件提交**

只有在潘总明确授权提交后执行：

```powershell
git add scripts/verify_platform_simple_model_access_v112.py tests/test_platform_simple_model_access_v112_verifier.py scripts/verify_platform_release_candidate_package.py tests/test_platform_release_candidate_package.py docs/superpowers/platform-product-rules.md docs/superpowers/platform-local-v1-acceptance-status.md docs/superpowers/platform-release-candidate-manifest.md docs/superpowers/platform-review-slices.md docs/CHANGELOG.md
git commit -m "docs: add V112 acceptance package"
```

## 6. 完成判定

只有以下条件全部满足，V112 才能标记完成：

1. PRO/MAX 可以购买 HK$28 加油包，支付成功只发放 168 Flash + 28 Pro，不改变会员等级。
2. 同一个支付事件重复到达不会重复发额度。
3. 会员基础额度先扣、加油包后扣；失败释放幂等且不会产生负数。
4. 加油包在当前会员月结束或会员到期时失效，页面付款前显示准确时间。
5. 用户只通过一个模型选择器切换平台、BYOK 和用户本地模型。
6. PRO/MAX 只能看到各自获准目录；PLUS 只能看到免费平台模型、自己的 API 和自己的本地模型。
7. BYOK 用户不需要输入 Base URL 或模型内部名，Key 永不由接口返回明文。
8. 用户本地模型只通过轻量连接器出站连接，不与 DSA 服务器 V107 Ollama 混用。
9. 同步、异步、重试、失败释放都使用同一模型选择和额度语义。
10. 中英文、多角色和 A/H/美股浏览器验收通过。
11. V112 验收器、release candidate、后端测试、前端测试、lint 和 build 全部通过。
12. 真实供应商或真实本地连接器未验收时，文档不升级对应状态。
13. 工作树中用户既有改动未被覆盖、删除或误提交。

## 7. 回滚方案

按影响从小到大执行：

1. 设置 `PLATFORM_USER_LOCAL_CONNECTOR_ENABLED=false`，隐藏用户本地入口并停止分配新本地任务；保留设备和历史任务记录。
2. 设置 `PLATFORM_MEMBER_MODEL_PICKER_ENABLED=false`，所有新分析回到平台推荐；不删除用户 Key。
3. 设置 `PLATFORM_BOOST_PACK_ENABLED=false`，停止创建新 checkout；已支付 grant 继续按原失效时间使用。
4. 回滚 Web 组件时保留新 API 响应字段，避免旧前端解析失败。
5. 新表和 additive 列不做破坏性删除；确认长期停用后另立数据迁移计划。
6. 发现额度错发时只通过审计流水做补偿或冻结，不直接删除用户记录。

## 8. 实施检查点

- V112-A 检查点：Task 1–5 完成后，先让用户验收“加油包 + 模型选择 + 三步 BYOK”。
- V112-B 检查点：Task 6–7 完成后，再让用户验收“一键 Ollama 连接器”。
- 最终检查点：Task 8 全部门禁通过后，才进入真实支付、真实供应商 Key 和签名连接器的受控验收。

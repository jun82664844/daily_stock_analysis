# DSA V111 Multi-provider BYOK Request Routing Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 让每次 `api_key_mode=user` 的股票分析都显式绑定当前用户、已保存的密钥记录、供应商和白名单模型，确保 DeepSeek、OpenAI、Anthropic 不再按固定顺序猜测或串用密钥。

**Architecture:** 在现有平台账号密钥表和分析主链之间增加一个请求级 BYOK 解析器。API 只接收 `provider`、`model`、`api_key_id`，解析器按 `user_id + api_key_id` 二次校验归属、启用状态、供应商、模型和服务端白名单；执行时复制基础配置，清空跨供应商回退、Router/Channel 和自定义 OpenAI Base URL，再只注入本次密钥与模型。同步和异步分析共用同一解析器及安全错误分类，前端从用户已保存且启用的密钥中选择，不允许手写任意 Base URL。

**Tech Stack:** FastAPI、Pydantic v2、SQLAlchemy/SQLite、cryptography/Fernet、LiteLLM、pytest/unittest、React 18、TypeScript、Zustand、Vitest/Testing Library。

---

## 正式上下文与范围

本计划以以下两份 2026-07-11 文档为正式产品上下文：

- `docs/superpowers/plans/2026-07-11-dsa-api-membership-and-byok-conversation-notes.md`
- `docs/superpowers/plans/2026-07-11-dsa-membership-api-pricing-market-research.md`

本切片只关闭“多供应商 BYOK 请求级路由”这一条链：

- `user` 模式必须同时提交 `provider`、`model`、`api_key_id`。
- 密钥记录必须属于当前登录用户、处于启用状态，并与提交的供应商和模型完全一致。
- 模型必须位于服务端配置的白名单中；白名单为空时 BYOK fail closed。
- 本次请求只可使用选中供应商的选中密钥，不得回退到平台密钥、其他用户密钥、其他供应商或任意中转 Base URL。
- DeepSeek、OpenAI、Anthropic 完成模拟路由、超时、余额不足、无权限、模型不存在、限流和隔离测试。
- V111 的 `local` 模式继续只代表 DSA 内部 V107 Ollama 开发/降级通道；PLUS、PRO、MAX 所称“用户自有本地模型”是另一条尚未实现的用户侧连接能力，不在 V111 中冒充已完成。
- 报告和页面继续使用“仅供信息分析，不构成投资建议”边界；本切片不新增买卖、仓位、目标价或收益承诺。

本切片不确定正式会员价格和额度，不连接真实支付，不写入真实 API Key，不执行真实 OpenAI/Claude 调用。真实供应商验收保留为受控人工门禁，待用户提供独立测试账号和明确授权后执行。

## 当前基线与脏树护栏

2026-07-12 核对结果：

- 当前分支：`local/dsa-upgrade-20260621-174728`。
- 工作树已有 V107 Ollama、V108 Kronos、V109 A 股数据、V110 全球股票数据等大量未提交改动。
- `AnalyzeRequest` 目前只有 `api_key_mode`，没有请求级 `provider`、`model`、`api_key_id`。
- `PlatformAccountService.apply_user_llm_config()` 目前按 `deepseek -> openai -> anthropic -> gemini` 顺序选择第一把可用密钥。
- `TaskInfo` 和异步队列目前只保存 `api_key_mode`。
- Web 已能保存多家供应商密钥，但分析提交只发送 `api_key_mode=user`。
- API Key 保存审计虽然经过统一脱敏器，调用点仍把原始 `api_key` 放入 metadata；V111 必须从调用点移除该字段。

实施时不得清理、回滚、覆盖或重新归属上述既有改动。每次修改前先运行：

```powershell
git status --short --branch
git diff --name-only
```

期望：看见现有脏树并保留；V111 只追加本计划列出的文件和必要的同链修改。

## 文件职责图

### 新建文件

- `src/services/byok_routing_service.py`：解析用户密钥选择、执行服务端模型白名单、构建只含本次供应商的请求级 Config。
- `tests/test_platform_byok_routing_v111.py`：后端请求契约、归属/启用/模型校验、同步/异步传播、配置隔离和配额行为。
- `tests/test_platform_byok_provider_errors_v111.py`：三供应商安全错误分类和密钥脱敏回归。
- `apps/dsa-web/src/components/platform/ByokRequestSelectorV111.tsx`：从已保存密钥中选择本次 BYOK 供应商/模型/密钥记录，并提供禁用和删除入口。
- `apps/dsa-web/src/components/platform/__tests__/ByokRequestSelectorV111.test.tsx`：选择、禁用、删除、无可用密钥和中英文提示测试。
- `scripts/verify_platform_multi_provider_byok_v111.py`：V111 静态/确定性验收器，成功输出 `DSA_PLATFORM_MULTI_PROVIDER_BYOK_V111_OK`。
- `tests/test_platform_multi_provider_byok_v111_verifier.py`：验收器及发布包可见性测试。

### 修改文件

- `.env.example`：增加显式 BYOK 模型白名单配置；默认空值代表关闭。
- `src/config.py`：解析白名单为规范化 `provider/model` 集合。
- `src/platform_accounts.py`：按 `user_id + api_key_id` 读取元数据/解密密钥，返回保存后的真实记录 ID，并增加启用/禁用/删除方法。
- `src/llm/errors.py`：增加 BYOK 供应商错误的安全分类，不回传原始 provider 文本。
- `src/services/analysis_service.py`：接收请求级 BYOK 字段并使用 BYOK 解析器；移除按固定顺序选第一把密钥的执行路径。
- `src/services/task_queue.py`：在内部任务对象中保存并传递 `provider`、`model`、`api_key_id`，但不在公开任务载荷中暴露密钥或解密结果。
- `api/v1/schemas/analysis.py`：为 `AnalyzeRequest` 增加请求级 BYOK 字段和跨字段校验。
- `api/v1/schemas/platform.py`：增加密钥启停请求模型。
- `api/v1/endpoints/analysis.py`：在扣配额前预检 BYOK 选择，并把选择传入同步/异步链。
- `api/v1/endpoints/platform.py`：增加启停/删除端点；保存审计只记录 ID、provider、model、enabled。
- `apps/dsa-web/src/types/analysis.ts`：增加 `ByokRequestSelection` 和分析请求字段。
- `apps/dsa-web/src/api/analysis.ts`：同步和异步请求序列化三项 BYOK 字段。
- `apps/dsa-web/src/api/platform.ts`：增加启停/删除密钥客户端方法。
- `apps/dsa-web/src/stores/stockPoolStore.ts`：保存当前 BYOK 选择；所有分析入口统一从 store 发送选择。
- `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`：覆盖完整选择传播和缺失选择前端阻断。
- `apps/dsa-web/src/api/__tests__/analysis.test.ts`：覆盖 snake_case 序列化和非 user 模式不发送 BYOK 字段。
- `apps/dsa-web/src/pages/HomePage.tsx`：把已保存密钥接入 V111 选择器；保存/禁用/删除后刷新选择。
- `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`：覆盖多家密钥切换、失效选择清理和实际分析提交。
- `tests/test_platform_api_keys_product.py`：覆盖真实记录 ID、审计不接收明文、启停/删除不越权。
- `tests/test_platform_accounts.py`：替换“固定顺序第一把密钥”测试为显式记录解析与配置隔离测试。
- `tests/test_analysis_api_contract.py`：覆盖新增请求字段、兼容边界和服务调用参数。
- `tests/test_platform_ai_feature_quota.py`：证明 BYOK 预检失败不扣额度，成功后只扣 user-key 服务器公平使用桶。
- `docs/superpowers/platform-product-rules.md`：记录 BYOK 请求级绑定、白名单和官方端点边界。
- `docs/superpowers/platform-local-v1-acceptance-status.md`：记录 V111 本地确定性验收状态和真实供应商待验门禁。
- `docs/superpowers/platform-release-candidate-manifest.md`：加入 V111 新文件、测试和验收器。
- `docs/superpowers/platform-review-slices.md`：新增 V111 独立 review slice。
- `scripts/verify_platform_release_candidate_package.py`：要求 V111 文件全部可见。
- `tests/test_platform_release_candidate_package.py`：覆盖 V111 missing-file 失败路径。
- `docs/CHANGELOG.md`：在 `[Unreleased]` 下按扁平格式增加 V111 新功能/安全/测试条目。

### 不修改文件

- 不修改 V107 Ollama 实现和 V108-V110 功能语义。
- 不修改真实支付、生产部署、港股实时行情授权或正式会员价格。
- 不新增用户自定义 Base URL 字段。
- 不保存真实供应商响应正文、请求 prompt、完整密钥或原始异常到审计/任务/历史记录。

---

### Task 1: 定义 BYOK 白名单和请求级解析器

**Files:**
- Create: `src/services/byok_routing_service.py`
- Modify: `src/config.py`
- Modify: `.env.example`
- Test: `tests/test_platform_byok_routing_v111.py`

- [ ] **Step 1: 先写白名单和解析器失败测试**

在 `tests/test_platform_byok_routing_v111.py` 建立临时数据库和用户，写出以下核心用例：

```python
def test_byok_model_allowlist_is_fail_closed_when_empty(self) -> None:
    key = self.accounts.store_api_key(
        self.user.id,
        provider="openai",
        api_key="sk-user-openai-secret",
        model="openai/test-model",
    )
    with self.assertRaisesRegex(ByokRoutingError, "byok_model_not_allowed"):
        self.router.resolve_selection(
            user_id=self.user.id,
            api_key_id=key["id"],
            provider="openai",
            model="openai/test-model",
            allowed_models=[],
        )

def test_provider_must_match_model_prefix_and_saved_record(self) -> None:
    key = self._store("anthropic", "anthropic/test-claude")
    with self.assertRaisesRegex(ByokRoutingError, "byok_provider_mismatch"):
        self.router.resolve_selection(
            user_id=self.user.id,
            api_key_id=key["id"],
            provider="openai",
            model="anthropic/test-claude",
            allowed_models=["anthropic/test-claude"],
        )
```

- [ ] **Step 2: 运行测试确认 RED**

Run:

```powershell
python -m pytest tests/test_platform_byok_routing_v111.py -q
```

Expected: FAIL，原因是 `src.services.byok_routing_service` 尚不存在或 Config 尚无白名单字段。

- [ ] **Step 3: 在 Config 中增加显式白名单**

在 `src/config.py` 的 AI 配置区增加：

```python
platform_byok_allowed_models: List[str] = field(default_factory=list)
```

在 `Config.from_env()` 解析：

```python
platform_byok_allowed_models = [
    item.strip().lower()
    for item in os.getenv("PLATFORM_BYOK_ALLOWED_MODELS", "").split(",")
    if item.strip()
]
```

并传入 Config 构造函数。`.env.example` 增加空白安全默认值：

```dotenv
# Comma-separated provider/model identifiers approved for user-owned API keys.
# Empty means BYOK model routing is disabled until an operator approves models.
PLATFORM_BYOK_ALLOWED_MODELS=
```

- [ ] **Step 4: 实现不可泄密的解析器类型**

`src/services/byok_routing_service.py` 至少定义：

```python
@dataclass(frozen=True)
class ByokSelection:
    api_key_id: int
    user_id: int
    provider: str
    model: str
    secret: str = field(repr=False)


class ByokRoutingError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(f"{code}: {message}")
```

`resolve_selection()` 必须按以下顺序验证：

```python
provider = (provider or "").strip().lower()
model = (model or "").strip()
if provider not in {"deepseek", "openai", "anthropic", "gemini"}:
    raise ByokRoutingError("byok_provider_not_allowed", "Provider is not approved")
if "/" not in model or model.split("/", 1)[0].lower() != provider:
    raise ByokRoutingError("byok_provider_mismatch", "Provider and model do not match")
if model.lower() not in {item.lower() for item in allowed_models}:
    raise ByokRoutingError("byok_model_not_allowed", "Model is not approved")
```

然后调用账号服务按 `user_id + api_key_id` 读取记录，验证 `enabled/provider/model`，最后解密。错误中不得包含明文、掩码以外的密钥、数据库路径或 provider 原始响应。

- [ ] **Step 5: 实现请求级 Config 隔离**

在 `build_scoped_config(base_config, selection)` 中先 `copy.copy()`，再清空所有平台和跨供应商路由：

```python
scoped.litellm_model = selection.model
scoped.litellm_fallback_models = []
scoped.agent_litellm_model = selection.model
scoped.litellm_config_path = None
scoped.llm_channels = []
scoped.llm_channel_names = []
scoped.llm_model_list = []
scoped.openai_base_url = None

for name in ("deepseek", "openai", "anthropic", "gemini"):
    setattr(scoped, f"{name}_api_keys", [])
    setattr(scoped, f"{name}_api_key", None)

setattr(scoped, f"{selection.provider}_api_keys", [selection.secret])
setattr(scoped, f"{selection.provider}_api_key", selection.secret)
```

测试必须证明基础 Config 未被修改、fallback/router/channel 被清空、OpenAI 自定义 Base URL 被清空、只有选中供应商包含用户密钥。

- [ ] **Step 6: 运行 Task 1 测试确认 GREEN**

Run:

```powershell
python -m pytest tests/test_platform_byok_routing_v111.py -q
python -m py_compile src/services/byok_routing_service.py src/config.py
```

Expected: PASS；没有网络请求。

- [ ] **Step 7: 经用户明确允许后再提交 Task 1**

```powershell
git add .env.example src/config.py src/services/byok_routing_service.py tests/test_platform_byok_routing_v111.py
git commit -m "feat: add request-scoped BYOK routing policy"
```

仓库规则要求未经明确确认不执行 commit；实施者只能把此步骤作为批准门禁。

---

### Task 2: 按用户和记录 ID 管理密钥生命周期

**Files:**
- Modify: `src/platform_accounts.py`
- Modify: `api/v1/schemas/platform.py`
- Modify: `api/v1/endpoints/platform.py`
- Test: `tests/test_platform_accounts.py`
- Test: `tests/test_platform_api_keys_product.py`

- [ ] **Step 1: 写记录 ID、归属、启停、删除和审计测试**

新增断言：

```python
saved = self.service.store_api_key(
    user.id,
    provider="openai",
    api_key="sk-user-openai-secret",
    model="openai/test-model",
)
self.assertIsInstance(saved["id"], int)

record = self.service.get_api_key_record(user.id, saved["id"])
self.assertEqual(record["provider"], "openai")
self.assertEqual(record["model"], "openai/test-model")
self.assertNotIn("secret", record)
self.assertEqual(
    self.service.get_api_key_secret_by_id(user.id, saved["id"]),
    "sk-user-openai-secret",
)
```

API 测试还要证明：用户 A 无法 PATCH/DELETE 用户 B 的记录；禁用后列表仍显示掩码记录但路由拒绝；删除后不可恢复；审计持久化 JSON 不含测试密钥片段。

- [ ] **Step 2: 运行测试确认 RED**

```powershell
python -m pytest tests/test_platform_accounts.py tests/test_platform_api_keys_product.py -q
```

Expected: FAIL，因为现有保存结果没有 ID，也没有按 ID 读取、启停和删除方法。

- [ ] **Step 3: 返回 upsert 后的真实记录**

`store_api_key()` 执行 upsert 后必须重新按 `user_id + provider` 查询，并返回：

```python
{
    "id": int(row.id),
    "provider": row.provider,
    "model": row.model,
    "masked_key": row.masked_key,
    "enabled": bool(row.enabled),
    "created_at": row.created_at.isoformat() if row.created_at else None,
    "updated_at": row.updated_at.isoformat() if row.updated_at else None,
}
```

保留当前“一名用户每个 provider 一条记录”的唯一约束；`api_key_id` 用于精确绑定，不在 V111 引入同一 provider 多密钥迁移。

- [ ] **Step 4: 增加按 ID 的所有权方法**

在 `PlatformAccountService` 增加以下所有权查询。元数据和解密值必须分开返回，避免普通字典的 `repr` 携带 secret：

```python
@staticmethod
def _api_key_payload(row: PlatformUserApiKey) -> dict:
    return {
        "id": int(row.id),
        "provider": row.provider,
        "model": row.model,
        "masked_key": row.masked_key,
        "enabled": bool(row.enabled),
        "created_at": row.created_at.isoformat() if row.created_at else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }

def get_api_key_record(self, user_id: int, api_key_id: int) -> Optional[dict]:
    with self.db.get_session() as session:
        row = session.execute(
            select(PlatformUserApiKey).where(
                and_(
                    PlatformUserApiKey.user_id == int(user_id),
                    PlatformUserApiKey.id == int(api_key_id),
                )
            )
        ).scalars().first()
        return self._api_key_payload(row) if row is not None else None

def get_api_key_secret_by_id(self, user_id: int, api_key_id: int) -> Optional[str]:
    with self.db.get_session() as session:
        row = session.execute(
            select(PlatformUserApiKey).where(
                and_(
                    PlatformUserApiKey.user_id == int(user_id),
                    PlatformUserApiKey.id == int(api_key_id),
                    PlatformUserApiKey.enabled.is_(True),
                )
            )
        ).scalars().first()
        encrypted = row.encrypted_secret if row is not None else None
    if not encrypted:
        return None
    try:
        return _load_fernet().decrypt(encrypted.encode("ascii")).decode("utf-8")
    except (InvalidToken, UnicodeDecodeError, ValueError):
        return None

def set_api_key_enabled(self, user_id: int, api_key_id: int, *, enabled: bool) -> Optional[dict]:
    with self.db.session_scope() as session:
        row = session.execute(
            select(PlatformUserApiKey).where(
                and_(
                    PlatformUserApiKey.user_id == int(user_id),
                    PlatformUserApiKey.id == int(api_key_id),
                )
            )
        ).scalars().first()
        if row is None:
            return None
        row.enabled = bool(enabled)
        row.updated_at = _utc_now()
        session.flush()
        return self._api_key_payload(row)

def delete_api_key(self, user_id: int, api_key_id: int) -> bool:
    with self.db.session_scope() as session:
        row = session.execute(
            select(PlatformUserApiKey).where(
                and_(
                    PlatformUserApiKey.user_id == int(user_id),
                    PlatformUserApiKey.id == int(api_key_id),
                )
            )
        ).scalars().first()
        if row is None:
            return False
        session.delete(row)
        return True
```

所有查询都必须同时过滤 `PlatformUserApiKey.user_id == user_id` 和 `PlatformUserApiKey.id == api_key_id`。`get_api_key_record()` 返回值不得出现 `encrypted_secret` 或 `secret`；只有路由器可调用 `get_api_key_secret_by_id()`，且不得记录返回值。

- [ ] **Step 5: 增加启停和删除 API**

`api/v1/schemas/platform.py`：

```python
class PlatformApiKeyStateRequest(BaseModel):
    enabled: bool
```

`api/v1/endpoints/platform.py`：

```python
@router.patch("/api-keys/{api_key_id}", response_model=PlatformApiKeyItem)
async def platform_set_api_key_state(
    request: Request,
    api_key_id: int,
    body: PlatformApiKeyStateRequest,
):
    _require_platform_csrf(request)
    identity = _require_identity(request)
    limited = check_platform_rate_limit(request, "api_keys", user_id=int(identity.user_id))
    if limited is not None:
        return limited
    item = PlatformAccountService().set_api_key_enabled(
        int(identity.user_id),
        api_key_id,
        enabled=body.enabled,
    )
    if item is None:
        return JSONResponse(status_code=404, content={"error": "api_key_not_found", "message": "API key not found"})
    _audit(
        user_id=int(identity.user_id),
        action="api_key_state_changed",
        metadata={"api_key_id": api_key_id, "provider": item["provider"], "model": item["model"], "enabled": item["enabled"]},
    )
    return item

@router.delete("/api-keys/{api_key_id}")
async def platform_delete_api_key(request: Request, api_key_id: int):
    _require_platform_csrf(request)
    identity = _require_identity(request)
    limited = check_platform_rate_limit(request, "api_keys", user_id=int(identity.user_id))
    if limited is not None:
        return limited
    service = PlatformAccountService()
    item = service.get_api_key_record(int(identity.user_id), api_key_id)
    if item is None or not service.delete_api_key(int(identity.user_id), api_key_id):
        return JSONResponse(status_code=404, content={"error": "api_key_not_found", "message": "API key not found"})
    _audit(
        user_id=int(identity.user_id),
        action="api_key_deleted",
        metadata={"api_key_id": api_key_id, "provider": item["provider"], "model": item["model"], "deleted": True},
    )
    return {"deleted": True}
```

两条写接口都必须验证 CSRF、登录和 rate limit；不存在或不属于当前用户统一返回 404。

- [ ] **Step 6: 从审计调用点移除原始 API Key**

把保存审计 metadata 改成：

```python
metadata={
    "api_key_id": item["id"],
    "provider": item["provider"],
    "model": item["model"],
    "enabled": item["enabled"],
}
```

PATCH/DELETE 同样只记录 ID、provider、model、enabled/deleted，不把 `body.api_key` 传给审计器。

- [ ] **Step 7: 运行账号和 API 测试**

```powershell
python -m pytest tests/test_platform_accounts.py tests/test_platform_api_keys_product.py -q
python -m py_compile src/platform_accounts.py api/v1/schemas/platform.py api/v1/endpoints/platform.py
```

Expected: PASS；测试数据库和审计事件都不包含明文密钥。

- [ ] **Step 8: 经用户明确允许后再提交 Task 2**

```powershell
git add src/platform_accounts.py api/v1/schemas/platform.py api/v1/endpoints/platform.py tests/test_platform_accounts.py tests/test_platform_api_keys_product.py
git commit -m "feat: bind BYOK keys to owned records"
```

---

### Task 3: 扩展分析 API 契约并在扣配额前预检

**Files:**
- Modify: `api/v1/schemas/analysis.py`
- Modify: `api/v1/endpoints/analysis.py`
- Test: `tests/test_analysis_api_contract.py`
- Test: `tests/test_platform_ai_feature_quota.py`
- Test: `tests/test_platform_byok_routing_v111.py`

- [ ] **Step 1: 写 AnalyzeRequest 跨字段测试**

覆盖以下契约：

```python
valid = AnalyzeRequest.model_validate({
    "stock_code": "AAPL",
    "apiKeyMode": "user",
    "provider": "openai",
    "model": "openai/test-model",
    "apiKeyId": 7,
})
self.assertEqual(valid.api_key_id, 7)

with self.assertRaises(ValidationError):
    AnalyzeRequest.model_validate({"stock_code": "AAPL", "apiKeyMode": "user"})

with self.assertRaises(ValidationError):
    AnalyzeRequest.model_validate({
        "stock_code": "AAPL",
        "apiKeyMode": "platform",
        "provider": "openai",
        "model": "openai/test-model",
        "apiKeyId": 7,
    })
```

- [ ] **Step 2: 运行契约测试确认 RED**

```powershell
python -m pytest tests/test_analysis_api_contract.py -q
```

Expected: FAIL，现有 schema 不接受或不校验三项选择。

- [ ] **Step 3: 增加显式字段与 validator**

在 `AnalyzeRequest` 增加：

```python
provider: Optional[Literal["deepseek", "openai", "anthropic", "gemini"]] = None
model: Optional[str] = Field(default=None, min_length=3, max_length=128)
api_key_id: Optional[int] = Field(
    default=None,
    ge=1,
    validation_alias=AliasChoices("api_key_id", "apiKeyId"),
)
```

使用 `@model_validator(mode="after")`：`user` 模式三项必须齐全；`platform/local` 模式三项必须全部为空。此处不接受 `base_url`、`api_base` 或 headers。

- [ ] **Step 4: 在扣额度前做无明文预检**

`trigger_analysis()` 在 `_reserve_platform_analysis_quota()` 之前调用仅校验元数据的 helper：

```python
selection_error = _validate_byok_request_selection(request, platform_user_id)
if selection_error is not None:
    return selection_error
```

预检必须再次验证当前用户、记录 ID、enabled、provider、model 和 Config 白名单，但不把解密后的 secret 放入 Request、日志或 JSONResponse。

- [ ] **Step 5: 把三项选择传给同步和异步入口**

同步调用 `AnalysisService.analyze_stock()` 以及异步 `submit_tasks_batch()` 都显式传：

```python
byok_provider=request.provider,
byok_model=request.model,
byok_api_key_id=request.api_key_id,
```

平台和本地模式传 `None`。

- [ ] **Step 6: 证明预检失败不扣配额**

在 `tests/test_platform_ai_feature_quota.py` 先记录 `ai_quick_user_key` 用量，提交错误所有者/禁用/不在白名单的选择，再断言用量不变；成功进入服务后只增加 user-key 公平使用桶，不增加平台模型桶。

- [ ] **Step 7: 运行 API 和配额测试**

```powershell
python -m pytest tests/test_analysis_api_contract.py tests/test_platform_ai_feature_quota.py tests/test_platform_byok_routing_v111.py -q
```

Expected: PASS；同步和异步均携带同一选择，预检失败为安全结构化错误且不扣额度。

- [ ] **Step 8: 经用户明确允许后再提交 Task 3**

```powershell
git add api/v1/schemas/analysis.py api/v1/endpoints/analysis.py tests/test_analysis_api_contract.py tests/test_platform_ai_feature_quota.py tests/test_platform_byok_routing_v111.py
git commit -m "feat: require explicit BYOK analysis selection"
```

---

### Task 4: 贯通异步队列和 AnalysisService，禁止跨供应商回退

**Files:**
- Modify: `src/services/task_queue.py`
- Modify: `src/services/analysis_service.py`
- Modify: `src/platform_accounts.py`
- Test: `tests/test_platform_accounts.py`
- Test: `tests/test_platform_byok_routing_v111.py`
- Test: `tests/test_analysis_api_contract.py`

- [ ] **Step 1: 写同步/异步精确传播测试**

测试构造同一用户的 OpenAI 和 Anthropic 两条记录，选 OpenAI 后断言：

```python
scoped = pipeline_cls.call_args.kwargs["config"]
self.assertEqual(scoped.litellm_model, "openai/test-model")
self.assertEqual(scoped.openai_api_keys, ["sk-user-openai-secret"])
self.assertEqual(scoped.anthropic_api_keys, [])
self.assertEqual(scoped.deepseek_api_keys, [])
self.assertEqual(scoped.litellm_fallback_models, [])
self.assertEqual(scoped.llm_model_list, [])
self.assertIsNone(scoped.openai_base_url)
```

异步测试在任务提交后、执行前禁用密钥，断言任务 fail closed，且没有使用平台 Config。

- [ ] **Step 2: 运行测试确认 RED**

```powershell
python -m pytest tests/test_platform_accounts.py tests/test_platform_byok_routing_v111.py tests/test_analysis_api_contract.py -q
```

Expected: FAIL，因为 TaskInfo 和服务签名尚未携带三项选择。

- [ ] **Step 3: 扩展内部 TaskInfo**

增加内部字段：

```python
byok_provider: Optional[str] = None
byok_model: Optional[str] = None
byok_api_key_id: Optional[int] = None
```

`copy()`、`submit_task()`、`submit_tasks_batch()`、`_execute_task()` 必须完整传播。`to_dict()` 不加入 secret，也不需要向公开任务列表暴露 `api_key_id`。

- [ ] **Step 4: 用解析器替换固定顺序选择**

`AnalysisService.analyze_stock()` 增加三项参数。`api_key_mode == "user"` 时：

```python
selection = ByokRoutingService(PlatformAccountService()).resolve_selection(
    user_id=platform_user_id,
    api_key_id=byok_api_key_id,
    provider=byok_provider,
    model=byok_model,
    allowed_models=config.platform_byok_allowed_models,
)
config = ByokRoutingService.build_scoped_config(config, selection)
```

没有完整选择、记录被禁用/删除、模型不匹配或解密失败时立即返回安全错误码。不得回落到 `apply_user_llm_config()` 的固定顺序逻辑。

- [ ] **Step 5: 收窄旧方法语义**

删除 `apply_user_llm_config()` 的执行调用；若仍有测试或非分析代码引用，先改为显式参数版本，或保留为抛出 `byok_selection_required` 的兼容壳。不得继续保留“找第一把密钥”的静默 fallback。

- [ ] **Step 6: 运行任务链测试**

```powershell
python -m pytest tests/test_platform_accounts.py tests/test_platform_byok_routing_v111.py tests/test_analysis_api_contract.py -q
python -m py_compile src/services/task_queue.py src/services/analysis_service.py
```

Expected: PASS；选 OpenAI 时不会装入 Anthropic/DeepSeek/Gemini 密钥，异步任务执行前会重新验证记录状态。

- [ ] **Step 7: 经用户明确允许后再提交 Task 4**

```powershell
git add src/services/task_queue.py src/services/analysis_service.py src/platform_accounts.py tests/test_platform_accounts.py tests/test_platform_byok_routing_v111.py tests/test_analysis_api_contract.py
git commit -m "fix: isolate provider routing for BYOK analysis"
```

---

### Task 5: 统一安全错误分类和三供应商失败矩阵

**Files:**
- Modify: `src/llm/errors.py`
- Modify: `src/services/analysis_service.py`
- Modify: `api/v1/endpoints/analysis.py`
- Create: `tests/test_platform_byok_provider_errors_v111.py`

- [ ] **Step 1: 写 provider 错误分类测试**

对 DeepSeek、OpenAI、Anthropic 分别参数化以下场景：

```python
CASES = [
    (TimeoutError("timed out sk-should-not-leak"), "byok_provider_timeout", 504),
    (Exception("401 invalid api key sk-should-not-leak"), "byok_provider_auth_failed", 400),
    (Exception("402 insufficient balance sk-should-not-leak"), "byok_provider_balance_required", 402),
    (Exception("403 permission denied sk-should-not-leak"), "byok_provider_permission_denied", 403),
    (Exception("404 model not found sk-should-not-leak"), "byok_provider_model_not_found", 400),
    (Exception("429 rate limit sk-should-not-leak"), "byok_provider_rate_limited", 429),
]
```

每个响应/任务错误/日志捕获结果都断言不含 `sk-should-not-leak` 和原始 provider response body。

- [ ] **Step 2: 运行测试确认 RED**

```powershell
python -m pytest tests/test_platform_byok_provider_errors_v111.py -q
```

Expected: FAIL，因为当前 user 模式最终可能返回通用 `analysis_failed` 和原始 `last_error`。

- [ ] **Step 3: 在 `src/llm/errors.py` 增加安全分类结果**

```python
@dataclass(frozen=True)
class ProviderFailure:
    code: str
    status_code: int
    message: str
    retryable: bool
```

`classify_byok_provider_error(error)` 只返回固定 code/message，不拼接 `str(error)`。优先判断异常类型/状态码，再使用小写文本标记；无法识别时返回 `byok_provider_failed`、502、固定消息。

- [ ] **Step 4: 同步和异步共用分类器**

`AnalysisService` 在 user 模式捕获异常或收到失败结果时，把 `last_error` 保存为固定 code，不保存原文。同步端点把 code 映射成固定 HTTP 状态和消息；异步任务只保存固定 code/message。

- [ ] **Step 5: 验证三供应商矩阵**

```powershell
python -m pytest tests/test_platform_byok_provider_errors_v111.py tests/test_platform_byok_routing_v111.py -q
```

Expected: PASS；三个 provider 的六类失败均安全、可区分且不泄密。

- [ ] **Step 6: 经用户明确允许后再提交 Task 5**

```powershell
git add src/llm/errors.py src/services/analysis_service.py api/v1/endpoints/analysis.py tests/test_platform_byok_provider_errors_v111.py
git commit -m "fix: sanitize BYOK provider failures"
```

---

### Task 6: 前端选择并发送精确密钥记录

**Files:**
- Create: `apps/dsa-web/src/components/platform/ByokRequestSelectorV111.tsx`
- Create: `apps/dsa-web/src/components/platform/__tests__/ByokRequestSelectorV111.test.tsx`
- Modify: `apps/dsa-web/src/types/analysis.ts`
- Modify: `apps/dsa-web/src/api/analysis.ts`
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `apps/dsa-web/src/stores/stockPoolStore.ts`
- Modify: `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`
- Modify: `apps/dsa-web/src/api/__tests__/analysis.test.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] **Step 1: 先写类型化序列化和 store 测试**

定义预期选择：

```typescript
const selection = {
  apiKeyId: 17,
  provider: 'anthropic',
  model: 'anthropic/test-claude',
} as const;
```

测试 `analysisApi.analyzeAsync()` 发送：

```typescript
expect(post).toHaveBeenCalledWith(
  '/api/v1/analysis/analyze',
  expect.objectContaining({
    api_key_mode: 'user',
    api_key_id: 17,
    provider: 'anthropic',
    model: 'anthropic/test-claude',
  }),
  expect.any(Object),
);
```

平台/本地模式断言 payload 不含三项 BYOK 字段；store 在 user 模式没有完整选择时不发请求，并设置可读错误。

- [ ] **Step 2: 运行前端测试确认 RED**

```powershell
cd apps/dsa-web
npm.cmd test -- --run src/api/__tests__/analysis.test.ts src/stores/__tests__/stockPoolStore.test.ts
```

Expected: FAIL，现有类型和 serializer 只有 `apiKeyMode`。

- [ ] **Step 3: 增加类型和 serializer**

`types/analysis.ts`：

```typescript
export type ByokProvider = 'deepseek' | 'openai' | 'anthropic' | 'gemini';

export interface ByokRequestSelection {
  apiKeyId: number;
  provider: ByokProvider;
  model: string;
}

export interface AnalysisRequest {
  byokSelection?: ByokRequestSelection;
}
```

`analysis.ts` 只在 `apiKeyMode === 'user'` 时展开：

```typescript
...(data.apiKeyMode === 'user' && data.byokSelection
  ? {
      api_key_id: data.byokSelection.apiKeyId,
      provider: data.byokSelection.provider,
      model: data.byokSelection.model,
    }
  : {}),
```

- [ ] **Step 4: 把选择放入 Zustand 单一真源**

`stockPoolStore.ts` 增加：

```typescript
byokSelection: ByokRequestSelection | null;
setByokSelection: (selection: ByokRequestSelection | null) => void;
```

`submitAnalysis()` 在 user 模式要求 `byokSelection` 完整，然后把它传给 API；platform/local 不发送。退出登录、密钥被禁用/删除或账号列表刷新后不再包含所选 ID 时，清空选择并回到 platform 模式。

- [ ] **Step 5: 增加密钥启停/删除客户端**

`platform.ts`：

```typescript
setApiKeyEnabled: async (apiKeyId: number, enabled: boolean): Promise<PlatformApiKeyItem> => {
  const response = await apiClient.patch(`/api/v1/platform/api-keys/${apiKeyId}`, { enabled });
  return toCamelCase<PlatformApiKeyItem>(response.data);
},

deleteApiKey: async (apiKeyId: number): Promise<{ deleted: boolean }> => {
  const response = await apiClient.delete(`/api/v1/platform/api-keys/${apiKeyId}`);
  return toCamelCase<{ deleted: boolean }>(response.data);
},
```

- [ ] **Step 6: 实现 V111 选择器**

`ByokRequestSelectorV111` 只展示 `enabled && id && model` 的记录。option 文案为 `Provider · model · maskedKey`；不提供 Base URL 输入。组件必须提供：

- 选择当前分析密钥；
- 禁用当前密钥；
- 删除前二次确认；
- 说明报告数据会发送到所选外部供应商；
- 中英文“仅供信息分析，不构成投资建议”提醒；
- 空列表时禁用 BYOK 并引导先保存获准供应商密钥。

- [ ] **Step 7: 接入 HomePage 的两个分析通道区域**

复用同一个组件，不复制第三套选择状态。保存密钥成功后，用返回的 `id/provider/model` 设为当前选择；禁用/删除后重新加载账号并清理失效选择。所有快速、深度、重新分析入口都从 store 读取相同选择。

- [ ] **Step 8: 运行前端 focused 测试**

```powershell
cd apps/dsa-web
npm.cmd test -- --run src/api/__tests__/analysis.test.ts src/stores/__tests__/stockPoolStore.test.ts src/components/platform/__tests__/ByokRequestSelectorV111.test.tsx src/pages/__tests__/HomePage.test.tsx
```

Expected: PASS；选择 Anthropic 时请求只发送 Anthropic 记录，禁用/删除后不能继续提交旧 ID。

- [ ] **Step 9: 运行 lint 和 build**

```powershell
cd apps/dsa-web
npm.cmd run lint
npm.cmd run build
```

Expected: PASS；无 TypeScript、ESLint 或构建错误。

- [ ] **Step 10: 经用户明确允许后再提交 Task 6**

```powershell
git add apps/dsa-web/src/components/platform/ByokRequestSelectorV111.tsx apps/dsa-web/src/components/platform/__tests__/ByokRequestSelectorV111.test.tsx apps/dsa-web/src/types/analysis.ts apps/dsa-web/src/api/analysis.ts apps/dsa-web/src/api/platform.ts apps/dsa-web/src/stores/stockPoolStore.ts apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts apps/dsa-web/src/api/__tests__/analysis.test.ts apps/dsa-web/src/pages/HomePage.tsx apps/dsa-web/src/pages/__tests__/HomePage.test.tsx
git commit -m "feat: select exact BYOK key per analysis"
```

---

### Task 7: 增加 V111 验收器、发布包和产品文档

**Files:**
- Create: `scripts/verify_platform_multi_provider_byok_v111.py`
- Create: `tests/test_platform_multi_provider_byok_v111_verifier.py`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/CHANGELOG.md`

- [ ] **Step 1: 先写验收器测试**

测试要求：

```python
result = subprocess.run(
    [sys.executable, "scripts/verify_platform_multi_provider_byok_v111.py"],
    cwd=REPO_ROOT,
    text=True,
    capture_output=True,
    check=False,
)
self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
self.assertIn("DSA_PLATFORM_MULTI_PROVIDER_BYOK_V111_OK", result.stdout)
```

再写 missing-file 测试，证明发布包清单缺少任一 V111 新文件时失败。

- [ ] **Step 2: 运行验收器测试确认 RED**

```powershell
python -m pytest tests/test_platform_multi_provider_byok_v111_verifier.py tests/test_platform_release_candidate_package.py -q
```

Expected: FAIL，因为脚本和清单尚未加入。

- [ ] **Step 3: 实现 V111 验收器**

验收器执行确定性测试，不访问真实供应商：

```python
FOCUSED_TESTS = [
    "tests/test_platform_byok_routing_v111.py",
    "tests/test_platform_byok_provider_errors_v111.py",
    "tests/test_platform_api_keys_product.py",
    "tests/test_platform_ai_feature_quota.py",
]

def main() -> int:
    run_checked([sys.executable, "-m", "pytest", *FOCUSED_TESTS, "-q"])
    print("DSA_PLATFORM_MULTI_PROVIDER_BYOK_V111_OK providers=deepseek,openai,anthropic live_keys=false")
    return 0
```

脚本不得读取或打印环境中的真实密钥；测试使用临时数据库和明显的假密钥。

- [ ] **Step 4: 更新发布包与 review slice**

在 manifest 中建立独立 `V111 Multi-provider BYOK Request Routing Package`，列出本计划的新增/修改测试和 verifier。`platform-review-slices.md` 单独列出：API contract、account ownership、runtime isolation、provider errors、Web selection、docs/package 六个 review 面。

- [ ] **Step 5: 更新产品规则和状态**

文档必须明确：

- GPT/Claude/DeepSeek BYOK 只有在 V111 确定性门禁通过且受控真实验收后，才能按对应供应商宣称可用。
- ChatGPT/Claude.ai 订阅不等于 API 额度。
- BYOK 不消耗平台模型额度，但仍受服务器、公平使用、数据源和防滥用上限约束。
- Ollama 只用于本地开发、自动测试、内部评估和内部降级。
- 正式会员等级为五级：游客、普通客户、PLUS、PRO、MAX。游客和普通客户免费；PLUS 为 HK$58/月、HK$158/季、HK$568/年；PRO 为 HK$78/月、HK$218/季、HK$888/年；MAX 为 HK$188/月、HK$558/季、HK$2,188/年。
- PLUS 保留普通客户每周 5 Flash + 每周 1 Pro 的免费赠送额度，但不增加额外付费平台额度；注册首月额外 1 Pro 不因升级 PLUS 而重复发放。PLUS 主要使用用户自己的 API 或未来的用户自有本地模型。PRO 由原每个会员月 98 Flash + 8 Pro 提高至 268 Flash + 28 Pro；MAX 每个会员月 1,688 Flash + 168 Pro。
- PRO 和 MAX 都维持接近 HK$50 的月均贡献利润且不赚 Token 差价，成本改善后优先增加查询次数。季度和年度额度按会员月发放，未用额度不退款、不折现、不结转，会员月结束或会员到期后失效。
- API 次数耗尽后允许有效 PRO/MAX 购买 API 加油包。初版建议为 HK$28/包，增加 168 Flash + 28 Pro，价格和两类次数都以“8”结尾，目标单包贡献利润率约 30%；加油包只补次数、不升级会员或模型权限，支付成功后以幂等账务流水入账，并在当前会员月结束或会员到期时失效。价格和次数待产品最终确认后锁定。
- BYOK 属于 PLUS、PRO、MAX 的有效会员能力。请求预检和实际模型调用前都必须复核会员 `expires_at`；到期前排队但尚未调用模型的任务不得在到期后继续执行 BYOK。
- 所有输出仅供信息分析，不构成投资建议。

- [ ] **Step 6: 更新 CHANGELOG**

在 `[Unreleased]` 直接追加扁平条目，不新增三级标题：

```markdown
- [新功能] 为用户自有 API 增加请求级供应商、模型和密钥记录绑定
- [修复] 禁止 BYOK 分析按固定供应商顺序串用密钥或回退到平台通道
- [测试] 增加 DeepSeek、OpenAI、Anthropic 路由隔离和安全错误验收
```

- [ ] **Step 7: 运行 V111 和发布包门禁**

```powershell
python scripts/verify_platform_multi_provider_byok_v111.py
python scripts/verify_platform_release_candidate_package.py
python -m pytest tests/test_platform_multi_provider_byok_v111_verifier.py tests/test_platform_release_candidate_package.py -q
```

Expected markers:

```text
DSA_PLATFORM_MULTI_PROVIDER_BYOK_V111_OK providers=deepseek,openai,anthropic live_keys=false
DSA_PLATFORM_RELEASE_CANDIDATE_PACKAGE_OK
```

- [ ] **Step 8: 经用户明确允许后再提交 Task 7**

```powershell
git add scripts/verify_platform_multi_provider_byok_v111.py tests/test_platform_multi_provider_byok_v111_verifier.py scripts/verify_platform_release_candidate_package.py tests/test_platform_release_candidate_package.py docs/superpowers/platform-product-rules.md docs/superpowers/platform-local-v1-acceptance-status.md docs/superpowers/platform-release-candidate-manifest.md docs/superpowers/platform-review-slices.md docs/CHANGELOG.md docs/superpowers/plans/2026-07-12-dsa-v111-multi-provider-byok-request-routing.md
git commit -m "docs: add V111 BYOK acceptance package"
```

---

### Task 8: 最终本地回归和受控真实验收门禁

**Files:**
- Verify only; do not store real credentials in repository files.

- [ ] **Step 1: 后端 focused + non-network 回归**

```powershell
python -m pytest tests/test_platform_byok_routing_v111.py tests/test_platform_byok_provider_errors_v111.py tests/test_platform_api_keys_product.py tests/test_platform_accounts.py tests/test_analysis_api_contract.py tests/test_platform_ai_feature_quota.py tests/test_platform_multi_provider_byok_v111_verifier.py -q
python -m pytest -m "not network" -q
```

Expected: PASS。若全量 non-network 因既有脏树失败，必须列出精确失败测试并证明是否与 V111 有关，不得把 skipped 当 passed。

- [ ] **Step 2: 前端 focused + lint + build**

```powershell
cd apps/dsa-web
npm.cmd test -- --run src/api/__tests__/analysis.test.ts src/stores/__tests__/stockPoolStore.test.ts src/components/platform/__tests__/ByokRequestSelectorV111.test.tsx src/pages/__tests__/HomePage.test.tsx
npm.cmd run lint
npm.cmd run build
```

Expected: PASS。

- [ ] **Step 3: 本地浏览器多角色验收**

用假密钥/模拟 provider 验证：游客和普通客户不能使用 BYOK；PLUS、PRO、MAX 可以保存三家密钥并精确切换，其中 PLUS 只继承普通客户免费赠送额度、不获得额外付费平台额度；管理员可查看脱敏 usage/audit。中英文模式都检查：供应商、模型、掩码、外部数据发送说明、仅供信息分析提示、错误文案。

Expected browser evidence:

```text
BYOK_BROWSER_ACCEPTANCE_OK roles=guest,free,plus,pro,max,admin providers=deepseek,openai,anthropic locales=zh,en secrets_exposed=false
```

截图只放 PR 描述、评论或外部验收证据，不写入仓库。

- [ ] **Step 4: 受控真实 OpenAI/Claude 验收保持人工门禁**

只有在用户明确授权并提供隔离测试账号后执行；通过进程环境临时注入密钥，不写 `.env`、文档、命令历史、日志或 Git。每家只发送一条最小、非敏感、信息分析测试请求，并检查供应商/模型、Token、耗时和固定错误结构。

验收结果只记录：

```text
provider=<openai|anthropic>
model=<approved provider/model>
request_succeeded=<true|false>
tokens_recorded=<true|false>
secret_exposed=<false>
information_only_boundary=<true>
```

没有执行真实验收时，状态必须保持：`REAL_OPENAI_CLAUDE_BYOK_NOT_VERIFIED`，不得宣传“GPT/Claude BYOK 已完全可用”。

- [ ] **Step 5: 检查差异和密钥痕迹**

```powershell
git diff --check
git status --short
rg -n --hidden -g '!apps/dsa-web/node_modules/**' -g '!node_modules/**' "sk-[A-Za-z0-9._-]{12,}|Bearer [A-Za-z0-9._-]{12,}" .
```

Expected: `git diff --check` 通过；搜索只允许命中明确的假密钥测试夹具或脱敏正则，不允许真实凭据。现有非 V111 脏树保持原状。

## 完成判定

只有同时满足以下条件才可声明 V111 本地完成：

1. user 模式缺少 `provider/model/api_key_id` 时 fail closed。
2. 同步和异步请求都按当前用户和记录 ID 二次校验。
3. 选 OpenAI 不会使用 Anthropic、DeepSeek、Gemini、平台 Router/Channel 或自定义 Base URL；其他供应商同理。
4. 禁用、删除、越权、provider/model 不匹配和白名单缺失都在扣配额前失败。
5. 三供应商六类失败矩阵不泄露密钥或原始 provider 响应。
6. 前端的所有分析入口使用同一 BYOK 选择；失效选择会清理。
7. 中英文页面都显示外部供应商数据发送说明和“仅供信息分析，不构成投资建议”边界。
8. V111 marker、发布包 marker、focused tests、前端 lint/build 通过，且 skipped 不计为通过。
9. 真实 OpenAI/Claude 未验收时明确保持未验证状态；真实密钥从未进入代码、文档、日志、审计、截图或 Git。
10. 没有清理、覆盖或误归属 V107-V110 及用户其他现有脏树改动。

## 后续独立切片

V111 完成后再分别规划，不与本切片混做：

- 统一各供应商结构化输出、语言切换、合规后处理和模型/数据来源展示。
- 汇总真实 Token、重试、缓存、耗时和实际成本，按 P50/P95 重算额度。
- 单独规划纯 Web 如何安全连接用户自有本地模型；未关闭该链前，PLUS 只开放 BYOK，不宣传本地模型已可用。
- 在至少 4 周真实数据后校准 PRO/MAX 查询额度，并持续检查各期限折算后的月均贡献利润约 HK$50；MAX 的 Token 成本改善优先让利为更多查询次数。
- 在取得正式市场数据分发授权前，不把港股实时串流行情混入基础会员权益。

# DSA V120 平台客服中心实施计划

> 状态：执行中。本阶段把 LukaAI 已验证的客服闭环按 DSA 技术栈原生移植；仅做本地产品功能，不共享 LukaAI 数据库，不涉及 AI 自动回复、生产部署、真实支付、生产密钥或投资建议。

## 目标

为 DSA 注册用户提供可追踪的文本客服工单，让用户能够提交问题、查看回复、继续沟通和关闭工单；为管理员提供统一待办队列、回复入口和状态流转，并保持用户数据隔离、审计可追踪和清晰的非投资建议边界。

## 产品边界

- V120 仅支持文本工单，不支持附件、图片、外部客服渠道或跨产品共享数据。
- 不接入模型、知识库或自动回复；所有管理员回复均为人工操作。
- 客服不得输出个股买卖指令、目标价、收益承诺或个性化投资建议。
- 普通用户只能访问自己的工单；管理员可访问全量工单，但审计元数据不得保存消息正文。
- 所有写请求复用 DSA 现有登录会话、CSRF 和按用户限流；不新增密钥或敏感配置。
- 本轮不修改 LukaAI 仓库，不执行生产部署、真实支付、数据转授权或真实备份清理。

## 数据契约

工单包含：

- `id`、`user_id`、`category`、`subject`。
- `status`：`open`、`in_progress`、`closed`。
- `unread_by_user`、`unread_by_admin`。
- `created_at`、`updated_at`、`closed_at`。

消息包含：

- `id`、`ticket_id`、`author_role`、`body`、`created_at`。
- `author_role` 仅允许 `user` 或 `admin`。
- 工单主题长度 4 至 120 字符；消息长度 2 至 4000 字符。

问题分类：

- `account`、`market_data`、`model`、`report`、`alerts`、`subscription`、`bug`、`other`。

## 任务清单

### 1. 后端契约测试先行

- [ ] 新增 `tests/test_platform_support_api_v120.py`。
- [ ] 覆盖未登录拒绝、CSRF、创建工单、用户列表/详情/回复/关闭、关闭后禁止回复。
- [ ] 覆盖跨用户访问拒绝、普通用户访问后台拒绝、管理员队列/详情/回复/状态更新。
- [ ] 覆盖未读状态、输入边界、限流和审计元数据不含消息正文。
- [ ] 先运行新测试并确认因能力尚未实现而失败。

验证：

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_support_api_v120
```

### 2. 数据模型、服务与 API

- [ ] 在 `src/storage.py` 新增独立客服工单和消息表，复用 `Base.metadata.create_all`。
- [ ] 新增 `src/services/platform_support_service.py`，集中处理所有权校验、状态流转、未读和序列化。
- [ ] 新增 `api/v1/schemas/support.py` 与 `api/v1/endpoints/support.py`。
- [ ] 在 `api/v1/router.py` 注册 `/support` 路由。
- [ ] 用户 API：创建、列表、详情、追加消息、关闭。
- [ ] 管理员 API：列表、详情、追加消息、更新状态。
- [ ] 写接口复用 CSRF、平台限流和结构化审计；审计仅记录工单 ID、分类和状态。

### 3. 前端测试先行

- [ ] 新增 `apps/dsa-web/src/api/__tests__/support.test.ts`。
- [ ] 新增 `apps/dsa-web/src/pages/__tests__/SupportPage.test.tsx`。
- [ ] 新增 `apps/dsa-web/src/components/admin/__tests__/SupportWorkbenchV120.test.tsx`。
- [ ] 更新路由与侧边栏测试，先确认新入口和交互测试失败。

验证：

```powershell
cd E:\DSA项目\apps\dsa-web
npm test -- --run src/api/__tests__/support.test.ts src/pages/__tests__/SupportPage.test.tsx src/components/admin/__tests__/SupportWorkbenchV120.test.tsx
```

### 4. 用户客服页与管理员工作台

- [ ] 新增 `apps/dsa-web/src/api/support.ts`，使用统一 `apiClient` 和 camelCase 转换。
- [ ] 新增 `/support` 路由、侧边栏客服入口和中英文文案。
- [ ] 新增 `SupportPage.tsx`，提供创建工单、列表、详情、回复和关闭闭环。
- [ ] 未登录时显示明确登录入口；加载、空态、错误、提交中和关闭态完整。
- [ ] 新增 `SupportWorkbenchV120.tsx` 并接入 `AdminPage.tsx`，提供状态筛选、未读提示、回复和状态操作。
- [ ] 桌面与移动端保持无横向溢出、无文字重叠，使用现有安静型运营界面风格。

### 5. V120 门禁与文档

- [ ] 新增 `scripts/verify_platform_support_center_v120.py` 与 `tests/test_platform_support_center_v120_verifier.py`。
- [ ] 更新 release package verifier 及其契约测试。
- [ ] 更新 `docs/platform-support-center.md`、`docs/CHANGELOG.md`、release manifest、产品规则、验收状态和 review slices。
- [ ] 新增 Playwright 工单闭环用例，覆盖用户提交与管理员处理的本地浏览器路径。

通过标记：

```text
DSA_PLATFORM_SUPPORT_CENTER_V120_OK user_loop=true admin_queue=true ownership_isolated=true csrf=true rate_limit=true ai_reply=false attachments=false investment_advice=false
```

### 6. 本地验收与工作树检查

- [ ] 运行后端专项测试和相关平台回归。
- [ ] 运行前端专项测试、lint 和 production build。
- [ ] 运行 V120 verifier 与 release package verifier。
- [ ] 启动本地服务，完成桌面与移动端浏览器验收并保存仓库外截图证据。
- [ ] 检查 `/health`、客服 API 和当前 Docker/本地运行状态，不修改生产配置。
- [ ] 执行敏感信息扫描、`git diff --check` 和完整脏树审计，清理仅由本轮产生的临时文件。
- [ ] 未获得潘总明确授权前，不提交、不推送；最终报告列出所有有意修改文件。

## 完成定义

只有在权限隔离、工单双向闭环、状态与未读语义、CSRF/限流、后端测试、前端测试、lint、构建、V120 verifier、发布包校验、桌面/移动浏览器验收和工作树审计全部成立时，V120 才能标记为本地实现完成。提交与推送是独立授权动作，不属于本轮默认完成条件。

# DSA 平台客服中心

## 范围

V120 将 LukaAI 已验证的工单闭环按 DSA 技术栈原生实现。两个项目不共享容器、数据库、会话或后台账号。

当前能力：

- 注册用户创建文本工单、查看列表和详情、追加消息、关闭工单。
- 管理员按状态查看队列、读取会话、人工回复和更新状态。
- 用户侧与管理员侧分别维护未读状态。
- 所有写请求复用平台会话、CSRF、按用户限流和结构化审计。

当前不包含：

- AI 自动回复、知识库检索、附件、图片、外部客服渠道或跨产品数据同步。
- 个股买卖指令、目标价、仓位、收益承诺或个性化投资建议。
- 生产部署、真实支付、生产密钥或市场数据转授权。

## 数据模型

`platform_support_tickets` 保存工单所有者、分类、主题、状态、双侧未读标记和时间戳。

`platform_support_messages` 保存工单消息、作者角色和创建时间。作者角色只能是 `user` 或 `admin`。

工单状态：

- `open`：等待处理。
- `in_progress`：管理员已回复或正在处理。
- `closed`：不可继续回复；管理员可显式重新打开。

## API

用户接口：

- `POST /api/v1/support/tickets`
- `GET /api/v1/support/tickets`
- `GET /api/v1/support/tickets/{ticket_id}`
- `POST /api/v1/support/tickets/{ticket_id}/messages`
- `POST /api/v1/support/tickets/{ticket_id}/close`

管理员接口：

- `GET /api/v1/support/admin/tickets`
- `GET /api/v1/support/admin/tickets/{ticket_id}`
- `POST /api/v1/support/admin/tickets/{ticket_id}/messages`
- `PATCH /api/v1/support/admin/tickets/{ticket_id}/status`

普通用户对非本人工单统一得到 404，避免暴露工单是否存在。管理员接口同时接受平台管理员会话和既有本地管理员会话。

## 安全与隐私

- 主题长度 4 至 120 字符，消息长度 2 至 4000 字符。
- 分类使用固定枚举，不接受任意内部路由或动作名。
- 关闭工单后用户和管理员都不能继续回复，必须由管理员先重新打开。
- 审计只记录工单 ID、分类和状态，不记录消息正文。
- 页面明确提示不要提交密码或 API Key；V120 不提供文件上传入口。
- 客服代码不导入或调用 LiteLLM、OpenAI、Anthropic、Ollama 或 Kronos。

## 前端入口

- 用户侧：`/support`，侧边导航显示“客服”。未登录时显示平台登录边界。
- 管理员侧：`/admin` 中的“客服工单”工作台。
- 中文和英文共用同一 API 与状态机；桌面和移动端使用响应式双栏/单栏布局。

## 本地验证

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe -m unittest tests.test_platform_support_api_v120
cd E:\DSA项目\apps\dsa-web
npm test -- --run src/api/__tests__/support.test.ts src/pages/__tests__/SupportPage.test.tsx src/components/admin/__tests__/SupportWorkbenchV120.test.tsx
npm run lint
npm run build
cd E:\DSA项目
E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_support_center_v120.py
```

通过标记：

```text
DSA_PLATFORM_SUPPORT_CENTER_V120_OK user_loop=true admin_queue=true ownership_isolated=true csrf=true rate_limit=true ai_reply=false attachments=false investment_advice=false
```

## 回滚

回滚前端入口时移除 `/support` 路由、导航项和管理员工作台。回滚 API 时移除 support router 注册；已有两张客服表可保留为只读历史，不需要删除真实数据或备份。

## V122 站内通知

- `GET /api/v1/support/summary` 只返回当前用户的未读回复数和未关闭工单数。
- `GET /api/v1/support/admin/summary` 只返回管理员未读数、待处理数和最早等待时间。
- 两个摘要都不包含工单主题、请求人邮箱或消息正文；游客不请求私有摘要。
- 侧边栏的“客服”显示新回复数，“运营”显示待处理工单数；大于 99 时显示 `99+`，可访问名称保留真实数量。
- 页面可见时每 60 秒轮询，页面隐藏时跳过；会话变化、工单操作和页面恢复可见时立即刷新。
- V122 不启用 WebSocket、AI 自动回复、邮件、短信、飞书或其他外部通知。

```powershell
E:\DSA项目\dsa-venv\Scripts\python.exe scripts\verify_platform_support_notifications_v122.py
```

```text
DSA_PLATFORM_SUPPORT_NOTIFICATIONS_V122_OK user_badge=true admin_badge=true polling=visible_only summary_redacted=true ai_reply=false external_notifications=false
```

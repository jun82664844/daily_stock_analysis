# DSA V122 客服站内通知与待办闭环 Implementation Plan

**Goal:** 在 V120 人工客服工单基础上补齐轻量站内提醒，让用户及时看到客服新回复，让管理员及时看到待处理工单，同时保持 local-first、无 AI、无外部通知依赖。

**Architecture:** 后端增加用户与管理员只读摘要接口，直接聚合现有工单未读和状态字段。前端侧边栏复用平台会话识别，页面可见时每 60 秒轮询，并在登录变化或工单操作后立即刷新。不开启 WebSocket，不拉取完整消息正文。

## 产品边界

- 用户仅能读取自己的未读数和处理中工单数。
- 管理员摘要仅返回未读、待处理数量和最早待处理时间，不返回消息正文。
- 游客不调用私有摘要接口。
- 页面隐藏时不执行轮询；重新可见后立即刷新。
- 不启用 AI 自动回复、邮件、短信、飞书或其他外部通知。
- 不新增投资建议、真实支付、生产部署或第三方密钥。

## Task 1: 摘要 API 测试先行

**Files:**

- Modify: `api/v1/schemas/support.py`
- Modify: `api/v1/endpoints/support.py`
- Modify: `src/services/platform_support_service.py`
- Create: `tests/test_platform_support_notifications_api_v122.py`

- [x] 写失败测试，覆盖用户隔离、管理员权限、未读计数、待处理计数和最早等待时间。
- [x] 实现 `GET /api/v1/support/summary`。
- [x] 实现 `GET /api/v1/support/admin/summary`。
- [x] 确认摘要不包含工单主题或消息正文。

## Task 2: 侧边栏徽标与轻量刷新

**Files:**

- Modify: `apps/dsa-web/src/api/support.ts`
- Modify: `apps/dsa-web/src/api/__tests__/support.test.ts`
- Modify: `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- Modify: `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`

- [x] 写失败测试，覆盖普通用户新回复徽标、管理员待处理徽标和游客零请求。
- [x] 登录变化、工单变更、页面恢复可见时立即刷新。
- [x] 页面可见时每 60 秒刷新，隐藏时跳过。
- [x] 徽标显示 `1-99` 和 `99+`，折叠侧边栏仍有可访问名称。

## Task 3: V122 门禁与验收

**Files:**

- Create: `scripts/verify_platform_support_notifications_v122.py`
- Create: `tests/test_platform_support_notifications_v122_verifier.py`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/platform-support-center.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [x] 新增 verifier 并先确认 RED。
- [x] 跑后端、前端、lint、build、桌面与移动浏览器验收。
- [x] 重启 `8018`，确认摘要路由、徽标、未读清除和管理员待办闭环。
- [x] 清理临时数据库、测试输出和临时服务。
- [x] 未经明确确认不 commit、不 push。

## 完成标记

```text
DSA_PLATFORM_SUPPORT_NOTIFICATIONS_V122_OK user_badge=true admin_badge=true polling=visible_only summary_redacted=true ai_reply=false external_notifications=false
```

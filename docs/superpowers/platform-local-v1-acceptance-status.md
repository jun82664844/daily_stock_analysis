# DSA Platform Local V1 验收状态

日期：2026-07-01

范围：本地优先的多用户平台基础版。此状态不是公网发布批准，不包含投资建议，也不代表已完成生产合规。

## 本轮新证据

本地已执行：

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_api tests.test_platform_accounts tests.test_platform_security_boundaries tests.test_platform_api_keys_product tests.test_platform_audit tests.test_platform_feature_policy tests.test_billing_api tests.test_local_v1_operability
cd apps\dsa-web
npm test -- --run src/api/__tests__/index.test.ts src/api/__tests__/platform.test.ts src/pages/__tests__/AdminPage.test.tsx
npm run build
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
git diff --check
```

观察结果：

- 后端指定 unittest：57 tests passed。
- 前端指定 vitest：3 test files / 8 tests passed。
- 前端 production build：`tsc -b && vite build` 通过。
- `verify_local_v1_operability.py` 默认门禁全部通过：basic query、feature quota、user API key mode、local model capacity、security boundaries、billing boundary、admin backend、admin frontend、frontend build、live health、live admin page。
- `git diff --check` 用于最终空白检查。

## 本地 V1 已覆盖

- 本地系统管理员、平台管理员、普通平台用户的后台访问边界已有测试覆盖。
- Cookie 写接口在 `PLATFORM_CSRF_ENABLED=true` 时校验 CSRF；平台登录和本地管理员登录会下发 CSRF cookie，退出会清理。
- 普通平台用户不能访问系统后台；平台管理员和已有本地 admin session 可查看用户、用量、审计日志并修改套餐。
- 用户 API Key 使用 Fernet 加密落库，接口响应和列表只返回 `masked_key`、provider、model、enabled、timestamps。
- 审计 metadata 会递归脱敏，AdminPage 渲染前再做一层客户端脱敏，避免历史污染记录展示明文 key/token。
- `free/pro/premium/enterprise` 计划边界已可测试；`premium` 保留为 `pro` 同档兼容别名。
- 平台 API、BYOK quick、BYOK deep、本地模型模式使用独立配额桶，避免把 BYOK/local 模式混入平台模型成本桶。
- 本地模型模式仍受 `LOCAL_LLM_MAX_CONCURRENT` 容量门控制。
- 本地 V1 支付接口保持禁用，checkout 和 webhook 仅保留边界契约。
- AdminPage 可展示用户、配额用量、审计事件和本地支付禁用状态，并覆盖空态、失败态、刷新和敏感 metadata 脱敏。

## 2026-07-02 用户端产品闭环增量

- 本地普通平台用户已补账户中心入口，可查看自己的 email、role、plan、基础 quota、功能 quota bucket、剩余额度、masked API Key 状态和推荐查询模式。
- 用户 API Key 保存/更新继续只返回 masked key；账户页和接口不展示明文 key、token、secret。
- 基础 snapshot 查询保持 no-AI，不消耗 AI quota；AI quick/deep、BYOK quick/deep、本地模型 lane 继续按独立 bucket 计量。
- 普通用户后端禁止访问 Admin 数据，前端平台会话识别为普通用户后隐藏 Admin 导航入口；历史记录按 `platform_user_id` 隔离。
- 本地支付沙箱仅在 `BILLING_ENABLED=true` 且 `BILLING_PROVIDER=sandbox` 时启用；checkout 返回本地 sandbox session，签名 webhook 可在测试中模拟 free -> pro 升级。缺失或错误签名会拒绝。
- 以上仍不代表公网可上线，不接真实支付，不构成投资建议。

## 2026-07-02 本地准生产 E2E 与风控补充
- 新增 Playwright 平台用户 E2E：普通用户注册/登录、账户页、保存测试 API Key、基础 no-AI 查询、BYOK quick 查询、历史记录、sandbox checkout、退出登录，以及 user A / user B 数据隔离。
- E2E 使用浏览器内 mock API 和占位测试 key，不使用真实 API Key，不连接真实支付，不截图/录制包含 secret 的失败附件。
- 普通用户注册/登录后的侧栏角色会刷新；普通用户看不到 Admin 导航，直接访问 admin API 返回 403。
- 平台用户切换后会重置并重新加载历史/股票栏，避免 A 用户历史或 masked key 残留给 B 用户。
- 后端关键写接口补充可配置本地限流：注册、API Key 保存、分析提交、sandbox checkout、billing webhook；429 统一返回 `rate_limited`、可读 `message` 和 `retry_after_seconds`。
- 新增 `scripts/cleanup_platform_e2e_data.py`，默认 dry-run，只允许 `e2e+` 邮箱命名空间，输出 matched count，不删除真实用户、真实历史报告或真实数据库。
- 新增 `scripts/verify_platform_user_e2e.py` 聚合后端安全测试、浏览器 E2E 与 dry-run 清理检查，通过时输出 `DSA_PLATFORM_USER_E2E_V1_OK`。
- 本阶段仍不代表公网可上线；真实支付、真实 API Key、生产部署、域名、HTTPS、WAF、邮件/短信、法律/隐私定稿和商业定价仍是上线前阻塞项。所有分析仅供信息分析，不构成投资建议。

## 2026-07-02 本地订阅账单生命周期补充
- 本地 sandbox billing 新增 checkout session、billing event、subscription state 持久化，用于本地订阅/账单生命周期验收。
- Signed webhook 支持 `checkout.completed`、`checkout.cancelled`、`checkout.expired`、`payment.failed`、`subscription.updated`；缺签或错签继续拒绝。
- Webhook 以 `provider_event_id` 幂等处理；重复事件返回 idempotent，不重复升级套餐，也不重复写入同一 provider event。
- `checkout.completed` 可在本地 sandbox 中让套餐生效；取消、失败、过期不升级；`subscription.updated` 仅允许 sandbox 测试对账到 `free/pro/premium/enterprise`。
- 用户账户页展示本地订阅状态、最近 sandbox session 和账单事件；管理员后台展示 sandbox billing event 摘要。普通用户不能访问管理员账单审计，也不能看到他人账单。
- 新增 `scripts/verify_platform_billing_lifecycle.py`，通过时输出 `DSA_PLATFORM_BILLING_LIFECYCLE_V1_OK`。本能力仍是本地 mock payment，不代表真实支付上线，不构成投资建议。

## 2026-07-02 查询质量与成本控制 V4 补充
- 统一 quick 查询入口新增市场路由元数据：A 股、美股、港股和加密货币分别进入 `a_share_market_data`、`us_market_data`、`hk_market_data`、`crypto_market_data` no-AI 数据通道。
- 基础 snapshot 继续不消耗 AI quota；前端会展示 route lane、quote freshness、均线、量价信号，并对 stale quote、missing quote、missing history 给出可读提示。
- Deep/AI 分析仍需用户显式点击 quick/deep action，并按 platform、BYOK、local model 选择消耗 `ai_quick`、`ai_deep`、`ai_quick_user_key`、`ai_deep_user_key` 或 `ai_local`。
- AI timeout 在同步分析接口中返回 `ai_timeout`/504；公共搜索失败可通过 diagnostic summary 暴露为降级警告，不应被包装成完整信息。
- 新增 `scripts/verify_platform_query_quality_v4.py`，通过时输出 `DSA_PLATFORM_QUERY_QUALITY_V4_OK`。本能力仍是本地准生产质量门，不代表公网可上线，不构成投资建议。

## 2026-07-02 本地功能跑通 V5 补充

- 新增 `tests/test_platform_local_functional_v5.py`，用临时 SQLite 和 TestClient 验证本地普通用户 quick/no-AI 多市场路由、deep/BYOK/local quota bucket、历史隔离、Admin 403 边界、sandbox billing summary 和 API Key 不泄漏。
- 新增 `scripts/verify_platform_local_functional_v5.py` 聚合本地功能门禁：8018 `/health`、页面 shell、`e2e+local-v5...` 注册/登录 smoke、账户页/API 边界、现有 V4/E2E/billing/release verifier；通过时输出 `DSA_PLATFORM_LOCAL_FUNCTIONAL_V5_OK`。
- live 行情 snapshot 仅作 optional smoke；若行情源不稳定必须报告 degraded，不能伪装成功。本阶段仍是本地功能版，不接真实支付，不提交真实 API Key，不构成投资建议。

## 仍非上线项

- 未接入真实支付、价格决策、商户账号、checkout 成功回调或套餐自动 reconciliation。
- 未完成公网生产部署、真实域名、HTTPS 证书、WAF/CDN、生产反向代理和生产日志/审计留存策略。
- 未接入邮件验证、短信验证、密码找回、外部账号登录或企业 SSO。
- 未完成生产密钥管理、轮换、备份恢复、数据库迁移演练、依赖/容器/暴露路由安全扫描。
- 未完成面向真实用户的法律条款、隐私政策和“仅供信息分析，不构成投资建议”的完整产品化展示。

## 2026-07-02 Local Usability V6 hard gate

- Added `tests/test_platform_local_usability_v6.py` for the V6 verifier contract.
- Added `scripts/verify_platform_local_usability_v6.py`; it prints `DSA_PLATFORM_LOCAL_USABILITY_V6_OK` only when required V5 local checks are fully passed.
- V6 turns stale live 8018 platform account or billing route failures, such as `/api/v1/platform/account` returning 404 after login, into hard failures instead of degraded success.
- Optional live market snapshot instability may still be reported as degraded diagnostics; the V6 optional multi-market quick smoke covers A-share, US, HK, and crypto no-AI routes and must not fake quote freshness.
- This remains local-only. It is not real payment, not public launch approval, not a real API Key handoff, and not investment advice.

## 2026-07-02 Local Query Speed V7 diagnostics gate

- Added `tests/test_platform_local_query_speed_v7.py` for the quick/no-AI timing, cache, source, freshness, and performance diagnostics contract.
- Added `scripts/verify_platform_local_query_speed_v7.py`; it prints `DSA_PLATFORM_LOCAL_QUERY_SPEED_V7_OK` only when V7 required local checks pass.
- `BasicQueryService.get_snapshot` now returns `diagnostics.elapsed_ms`, quote/history elapsed time, cache hit/miss state, source, freshness, route lane, and performance status while keeping `ai_used=false`.
- HomePage displays compact quick-query diagnostics so local users can see whether a query is fresh/cached and where latency is coming from.
- V7 remains local-only. It does not enable production deployment, real payment, real API Key custody changes, or public SearXNG. All analysis remains informational only and is not investment advice.

## 2026-07-02 Local Query Resilience V8 timeout/fallback gate

- Added `tests/test_platform_local_query_resilience_v8.py` for bounded quick-source timeout behavior and stale-cache fallback diagnostics.
- Added `scripts/verify_platform_local_query_resilience_v8.py`; it prints `DSA_PLATFORM_LOCAL_QUERY_RESILIENCE_V8_OK` only when V8 required local checks pass.
- Quick/no-AI quote and history fetches now use a bounded local timeout. Slow sources degrade to `quote_timeout` or `history_timeout` warnings instead of blocking the UI or invoking AI.
- Diagnostics now include `timeouts`, sanitized `errors`, and `fallback` states such as `live`, `cache`, `stale_cache`, or `none`.
- HomePage displays compact fallback state for quote/history. It does not display raw exceptions, headers, tokens, URLs with keys, or API keys.
- V8 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-02 Local Market Source Health V9 gate

- Added `tests/test_platform_local_market_source_health_v9.py` for source-health cooldown, prewarm cache behavior, prewarm endpoint summary, and source-health diagnostics.
- Added `scripts/verify_platform_local_market_source_health_v9.py`; it prints `DSA_PLATFORM_LOCAL_MARKET_SOURCE_HEALTH_V9_OK` only when V9 required local checks pass.
- Quick/no-AI quote and history sources now record local source health. Repeated source failures enter a bounded `cooling_down` state so later quick queries can skip live calls instead of repeatedly blocking.
- Added local no-AI prewarm support for a small symbol set across A-share, US, HK, and crypto lanes. Prewarm does not call AI and does not consume AI quota.
- Diagnostics now include `source_health` for quote/history. HomePage shows compact source-health status and does not display raw exceptions, headers, tokens, URLs with keys, or API keys.
- V9 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-02 Local Persistent Market Cache V10 gate

- Added `tests/test_platform_local_persistent_market_cache_v10.py` for disk-backed quick-query cache persistence, stale disk-cache fallback, source-health compatibility, and persistent-cache diagnostics.
- Added `scripts/verify_platform_local_persistent_market_cache_v10.py`; it prints `DSA_PLATFORM_LOCAL_PERSISTENT_MARKET_CACHE_V10_OK` only when V10 required local checks pass.
- Quick/no-AI snapshots now use a small local JSON-backed market cache by default. This reduces repeated public-source calls after WebUI restart or source cooldown.
- Diagnostics now include `persistent_cache` with memory/disk state and `local_json` mode. The UI shows compact persistent-cache status and does not display absolute paths, headers, tokens, URLs with keys, or API keys.
- Disk-cache fallbacks are labeled as `disk_cache` or `stale_disk_cache`; stale cache remains a visible degraded state, not a fake fresh quote.
- V10 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-02 Local Market Source Ops V11 gate

- Added `src/services/market_source_ops.py` as a read-only local source priority and health summary for A-share, US, HK, and crypto quick-query lanes.
- Added `GET /api/v1/stocks/sources/health`; it returns route lane, quote/history source priority, source health, cooldown, latency, cache mode, and `ai_used=false` without invoking live quote/history fetches.
- AdminPage now shows a local "Market source health" panel with source priority, status, latency, cooldown, and persistent-cache mode so operators can see why a lane is slow or degraded.
- Added `tests/test_platform_local_market_source_ops_v11.py` and `scripts/verify_platform_local_market_source_ops_v11.py`; the verifier prints `DSA_PLATFORM_LOCAL_MARKET_SOURCE_OPS_V11_OK` only when required local checks pass.
- V11 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-02 Local Market Prewarm Console V12 gate

- AdminPage now includes a local "Prewarm market cache" action for `600519`, `AAPL`, `HK00700`, and `BTC-USD`.
- The action reuses the existing no-AI prewarm endpoint and displays the latest requested/warmed/degraded/elapsed/no-AI summary in the market-source panel.
- After a successful prewarm, AdminPage refreshes market source health so operators can immediately inspect cache mode, source priority, cooldown, and latency state.
- Added `tests/test_platform_local_market_prewarm_console_v12.py` and `scripts/verify_platform_local_market_prewarm_console_v12.py`; the verifier prints `DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK` only when required local checks pass.
- V12 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Market Recovery Console V13 gate

- Added admin-only `POST /api/v1/stocks/sources/recovery`; ordinary platform users receive 403 and cannot reset market-source health state.
- Recovery resets selected in-memory market-source cooldown state only. It does not purge persistent market cache files, reports, history, database rows, API keys, billing data, or user data.
- Recovery can optionally run the existing no-AI prewarm path for `600519`, `AAPL`, `HK00700`, and `BTC-USD`; both recovery and prewarm responses keep `ai_used=false`.
- AdminPage now includes a local "Recover local sources" action and shows latest recovery reset/prewarm/no-AI summary before refreshing market source health.
- Added `tests/test_platform_local_market_recovery_console_v13.py` and `scripts/verify_platform_local_market_recovery_console_v13.py`; the verifier prints `DSA_PLATFORM_LOCAL_MARKET_RECOVERY_CONSOLE_V13_OK` only when required local checks pass.
- V13 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Real Use Loop V14 gate

- Added admin-only `GET /api/v1/platform/admin/local-status`; ordinary platform users receive 403 and cannot read the local operator status.
- The local status payload is read-only and keeps `mode=local_only` and `ai_used=false`. It summarizes 8018 service status, auth flags, billing boundary, AI/BYOK/local-model mode, public-search state, market cache/source status, and safety flags.
- The status payload does not return API keys, bearer tokens, cookies, admin passwords, or local secret paths. Test coverage injects secret-like environment values and verifies they are not present in the response.
- AdminPage now includes a "Local functional status" panel showing 8018 readiness, cache mode, no-AI status, BYOK support, local-model state, public-search state, real-payment state, and secret-redaction state.
- Added `tests/test_platform_local_real_use_loop_v14.py` and `scripts/verify_platform_local_real_use_loop_v14.py`; the verifier prints `DSA_PLATFORM_LOCAL_REAL_USE_LOOP_V14_OK` only when required local checks pass. Optional live smoke may create `e2e+` local admin/user accounts and must not print generated passwords.
- V14 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local User Query Loop V15 gate

- HomePage ordinary-user mode now loads the richer account summary when available, including plan, weekly free quota, quota buckets, masked API key state, and recommended query mode. If `/api/v1/platform/account` is unavailable in an older local process, it falls back to the existing session and masked API key list instead of breaking the page.
- HomePage now shows a user-query status strip for signed-in users: signed-in email, plan, weekly quota, no-AI quick-query quota, masked BYOK readiness, and recommended mode. It does not render plaintext API keys or bearer tokens.
- Basic quick snapshots now show a compact guardrail strip: current quick snapshot, no-AI/AI-used state, market data lane, local cache mode when present, and a reminder that historical reports stay separate from the current snapshot.
- The quick snapshot path remains no-AI. Quick/Deep AI buttons remain explicit user actions and are labeled as consuming the selected platform, BYOK, or local-model quota.
- Added `tests/test_platform_local_user_query_loop_v15.py` and `scripts/verify_platform_local_user_query_loop_v15.py`; the verifier prints `DSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK` only when required local checks pass. Optional live quick snapshot checks may report degraded source availability and must not fake freshness.
- V15 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Browser User Loop V16 gate

- Playwright platform user E2E now asserts the visible ordinary-user query guardrails in the browser: account status strip, masked BYOK readiness, no-AI quick-query status, market lane labels, local cache mode, and history separation.
- The browser flow covers A-share `600519`, US `AAPL`, HK `HK00700`, and crypto `BTC-USD` quick snapshots without invoking AI, then uses the top-toolbar BYOK quick-analysis action to verify BYOK quota separation.
- The E2E flow also keeps ordinary users away from Admin navigation/API, proves AccountPage does not reveal plaintext API keys, exercises local sandbox checkout copy, and re-checks A/B user history/API-key isolation.
- Added `tests/test_platform_local_browser_user_loop_v16.py` and `scripts/verify_platform_local_browser_user_loop_v16.py`; the verifier prints `DSA_PLATFORM_LOCAL_BROWSER_USER_LOOP_V16_OK` only when required local checks pass.
- The V16 verifier also creates an `e2e+` local smoke user for optional live 8018 multi-market no-AI snapshots. Public-source slowness or stale data may be reported as degraded diagnostics and must not be faked as fresh success.
- V16 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Watchlist V17 gate

- Added a platform-user private watchlist table and `src/platform_watchlist.py`; this is separate from the global `STOCK_LIST` config watchlist.
- Added `GET/POST/DELETE /api/v1/platform/watchlist` and `POST /api/v1/platform/watchlist/refresh`. Ordinary users only see their own symbols.
- Watchlist refresh uses the existing no-AI quick snapshot path for A-share, US, HK, and crypto lanes, returns route/freshness/degradation summaries, and does not consume AI quota.
- HomePage now shows a private watchlist panel for signed-in platform users, supports adding the current query, and displays a no-AI multi-market refresh summary.
- Added `tests/test_platform_local_watchlist_v17.py`, `tests/test_platform_local_watchlist_v17_verifier.py`, and `scripts/verify_platform_local_watchlist_v17.py`; the verifier prints `DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK` only when required checks pass.
- V17 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Watchlist Board V18 gate

- HomePage now renders refreshed platform watchlist rows as a compact board for signed-in local platform users.
- Board rows show stock code, name, market, price, change percent, freshness, route lane, no-AI state, degradation status, and warning codes for A-share, US, HK, and crypto symbols.
- Each board row can trigger the existing quick snapshot query for that symbol. This reuses the no-AI quick path and does not call deep/AI analysis.
- Added `tests/test_platform_local_watchlist_board_v18.py` and `scripts/verify_platform_local_watchlist_board_v18.py`; the verifier prints `DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK` only when required checks pass.
- V18 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Query Workspace V19 gate

- HomePage now shows a query workspace status band inside the current quick snapshot panel.
- The status band separates `Current Snapshot`, `Watchlist`, `History Reports`, and `AI Analysis` state so ordinary users can see which result is fresh, private, historical, or AI-related.
- Current snapshots remain no-AI and show their market lane. Watchlist state shows private symbol count. History state remains separate from the current snapshot. AI state shows the selected platform/BYOK/local mode and BYOK readiness.
- Added `tests/test_platform_local_query_workspace_v19.py` and `scripts/verify_platform_local_query_workspace_v19.py`; the verifier prints `DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK` only when required checks pass.
- V19 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Public Entry V20 gate

- The frontend App route guard now allows ordinary platform-user routes such as `/`, `/portfolio`, `/chat`, `/account`, and `/usage` to render without an admin cookie.
- `/admin` and `/settings` remain admin-only frontend routes and still redirect to the admin login page when no admin session is present.
- The frontend API 401 interceptor no longer sends public platform entry pages to the admin login when ordinary platform-user/account APIs return unauthenticated responses.
- Public unauthenticated navigation no longer shows admin-only nav entries or the admin logout action.
- Public unauthenticated history and market-review history initialization now degrades to empty state instead of showing `Login required` as a page-level error.
- This fixes the local 8018 browser finding where the root page showed the admin login screen and blocked ordinary users from reaching platform login/register/query UI.
- Added `tests/test_platform_local_public_entry_v20.py` and `scripts/verify_platform_local_public_entry_v20.py`; the verifier prints `DSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_OK` only when route-boundary, V19 compatibility, verifier tests, App route guard tests, API 401 redirect guard tests, public navigation guard tests, and public-history 401 empty-state tests pass.
- V20 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Public User Flow V21 gate

- Added `tests/test_platform_local_public_user_flow_v21.py` and `scripts/verify_platform_local_public_user_flow_v21.py`; the verifier prints `DSA_PLATFORM_LOCAL_PUBLIC_USER_FLOW_V21_OK` only when required local checks pass.
- V21 verifies the ordinary-user public loop: local register/login, account summary, quota bucket presence, masked API key state, A-share/US/HK/crypto no-AI quick route, private watchlist add/refresh, and ordinary-user admin 403 boundary.
- The optional live 8018 smoke may create `e2e+local-v21...` users and must not print generated passwords. Market-source stale/unavailable states remain visible diagnostics and must not be faked as fresh success.
- Browser verification on local 8018 confirmed public entry, test-user registration, 600519 no-AI quick query, query-workspace separation, and watchlist add/refresh without showing Admin navigation.
- V21 remains local-only. It is not public launch approval, not real payment, not production secret handling, and not investment advice.

## 2026-07-03 Local Market Refresh V22 gate

- Added `tests/test_platform_local_market_refresh_v22.py` and `scripts/verify_platform_local_market_refresh_v22.py`; the verifier prints `DSA_PLATFORM_LOCAL_MARKET_REFRESH_V22_OK` only when required local checks pass.
- `GET /api/v1/stocks/{symbol}/snapshot` remains cache-first and no-AI. `GET /api/v1/stocks/{symbol}/snapshot?refresh=true` bypasses snapshot cache, fetches deterministic market data, updates cache, and returns refresh diagnostics.
- HomePage now shows a manual current-snapshot refresh button after a quick query. Refresh calls `snapshot?refresh=true`, renders `force_refresh` diagnostics, and does not submit AI analysis.
- Optional live 8018 refresh smoke may report degraded market-source behavior; it must not fake fresh data when upstream quote/history sources fail.
- V22 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, and not investment advice.

## 2026-07-03 Local History Snapshot Boundary V23 gate

- Added `tests/test_platform_local_history_snapshot_boundary_v23.py` and `scripts/verify_platform_local_history_snapshot_boundary_v23.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_SNAPSHOT_BOUNDARY_V23_OK` only when required local checks pass.
- HomePage historical report view now shows `Historical AI report` and `not current quote` boundary copy so users do not confuse old AI reports with current quote data.
- Historical stock reports now offer a current-quote refresh action that calls the no-AI `snapshot?refresh=true` path, renders the current snapshot view after refresh, and does not submit AI analysis.
- V23 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, and not investment advice.

## 2026-07-03 Local History Center V24 gate

- Added `tests/test_platform_local_history_center_v24.py` and `scripts/verify_platform_local_history_center_v24.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V24_OK` only when required local checks pass.
- HomePage now mounts a dedicated History Center in the sidebar using the existing `HistoryList` component.
- The History Center filters loaded local reports by market/code/report type/time/refresh status and sorts by generated time.
- Historical report cards show `Not refreshed` by default and switch to `Current quote refreshed` only after the no-AI current quote refresh succeeds.
- The refresh marker is session-only. It does not rewrite old AI reports and does not delete history reports, databases, user data, or cached reports.
- V24 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, and not investment advice.

## 2026-07-03 Local History Center V25 gate

- Added `tests/test_platform_local_history_center_v25.py` and `scripts/verify_platform_local_history_center_v25.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V25_OK` only when required local checks pass.
- `/api/v1/history` now supports backend filtering for market, refresh status, stable sort, code, report type, and time range so the History Center is not limited to the currently loaded frontend page.
- Added a side-table persistent refresh marker for no-AI current quote refreshes. It is scoped by platform user and history record.
- `/api/v1/history/{record_id}/refresh-marker` rejects `ai_used=true`, prevents ordinary users from marking another user's record, and does not rewrite old AI reports.
- HomePage maps History Center controls into backend query params and writes the persistent marker after `snapshot?refresh=true` succeeds.
- V25 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-03 Local History Center V26 gate

- Added `tests/test_platform_local_history_center_v26.py` and `scripts/verify_platform_local_history_center_v26.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V26_OK` only when required local checks pass.
- History Center filters are now restored from validated browser `localStorage` state and re-applied through the backend-filtered history API.
- `stockPoolStore` now tracks backend `historyTotal`, `useHomeDashboardState` exposes it, and `HistoryList` can display the backend total instead of only the currently loaded page count.
- The focused HomePage test covers restored market/code/report type/time/refresh/sort filters, backend filter params, and `history-total-count` display.
- V26 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Local History Export V27 gate

- Added `tests/test_platform_local_history_export_v27.py` and `scripts/verify_platform_local_history_export_v27.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_EXPORT_V27_OK` only when required local checks pass.
- `POST /api/v1/history/export` exports selected owner-scoped local history records as Markdown or JSON without invoking AI and returns `ai_used=false`.
- Export record IDs are de-duplicated, capped at 50, and ordinary platform users cannot export another user's records.
- Export content is redacted for secret-like strings and JSON export does not dump raw_result or API keys.
- HomePage History Center selection is enabled and can download selected reports as a browser-local Markdown bundle.
- V27 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Local History State V28 gate

- Added `tests/test_platform_local_history_state_v28.py` and `scripts/verify_platform_local_history_state_v28.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_STATE_V28_OK` only when required local checks pass.
- Added the side table `analysis_history_user_states` for owner-scoped favorite, important, archived, read, and note state.
- `PATCH /api/v1/history/{record_id}/state` and `PATCH /api/v1/history/state` update local report-management state without invoking AI and return `ai_used=false`.
- `/api/v1/history?state=...` supports favorite, important, archived, active, has_note, unread, and read filtering.
- HomePage History Center now has a state filter, batch archive/restore buttons, detail favorite/important/read/archive controls, and local note saving.
- V28 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Local History Operations V29 gate

- Added `tests/test_platform_local_history_ops_v29.py` and `scripts/verify_platform_local_history_ops_v29.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_OPS_V29_OK` only when required local checks pass.
- History Center now defaults to the active lane so archived records are not mixed into ordinary browsing.
- `/api/v1/history?note_search=...` filters owner-scoped local notes without invoking AI.
- HomePage History Center now has a note search input, date group headers, batch important, and batch read actions.
- Note search and batch important/read remain no-AI local report-management operations and must not consume AI quota.
- V29 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Local History Detail V30 gate

- Added `tests/test_platform_local_history_detail_v30.py` and `scripts/verify_platform_local_history_detail_v30.py`; the verifier prints `DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK` only when required local checks pass.
- Historical report detail now has report detail search, search match navigation, section jumps, and a same-stock timeline.
- Same-stock timeline reuses existing owner-scoped history list data and does not add a new backend timeline endpoint.
- Report detail search, section jumps, and timeline navigation remain no-AI local read operations and must not consume AI quota.
- `ReportSummary` exposes stable section anchors through `sectionIdPrefix` for local detail navigation.
- V30 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Public Quick Snapshot V31 gate

- Added `tests.test_basic_query_no_ai.BasicQueryNoAiTestCase.test_snapshot_is_public_without_platform_login` so anonymous visitors can run `GET /api/v1/stocks/{symbol}/snapshot` without a platform session.
- The public snapshot path remains GET-only and no-AI: it must not call `AnalysisService`, consume AI quota, expose BYOK keys, write private watchlist/history ownership state, or hide stale/missing market-data warnings.
- Account center, private history, watchlist persistence, BYOK save/use, quick/deep AI analysis, sandbox billing, and admin/operator APIs remain login- and permission-protected.
- `scripts/verify_platform_query_quality_v4.py` now checks the public snapshot boundary markers alongside the existing multi-market no-AI route tests.
- V31 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Public Page Recovery V32 gate

- Added a RouteBoundary guard for local frontend build swaps: if a lazy route chunk fails with a dynamic-import/chunk-load error, the page attempts one automatic reload for that exact chunk signature.
- Added `apps/dsa-web/src/components/layout/__tests__/RouteBoundary.test.tsx` coverage so chunk-load recovery calls reload once while ordinary route render errors still show the existing recoverable error page.
- Rebuilt local static assets after the fix. Fresh browser automation on 8018 opens the public homepage, runs an anonymous `AAPL` quick snapshot, and renders `No AI` / `US market data` without the route error page.
- V32 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Public Page Recovery V33 gate

- RouteBoundary recovery now navigates to the current URL with `dsa_route_reload=<timestamp>` instead of using a plain browser reload. This forces Chrome to fetch the current local bundle after repeated frontend rebuilds.
- The manual `重新加载页面` action and one-shot chunk-load recovery share the same cache-busting path.
- Added test coverage for cache-busting recovery URL construction and rebuilt local static assets. Fresh browser automation on 8018 with a cache-bust query opens the homepage and runs anonymous `AAPL` quick snapshot with `No AI` / `US market data`.
- V33 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-04 Browser State Recovery V34 gate

- Added backend `/reset-ui` as a React-independent recovery page. It clears browser-side UI storage/cache/service-worker state for the local 8018 origin and redirects to `/?dsa_route_reload=<timestamp>&dsa_ui_reset=1`.
- The reset page uses no-store headers and does not delete reports, databases, server-side user data, API keys, or market cache files.
- Updated the frontend HTML template to `lang="zh-CN"`, `translate="no"`, and `notranslate` metadata to reduce Chrome Translate DOM mutation risk on the local React page.
- Live 8018 verification opened `/reset-ui`, redirected to the refreshed homepage, ran anonymous `AAPL` quick snapshot, and rendered `No AI` / `US market data` without the route error page.
- V34 remains local-only. It is not public launch approval, not real payment, not production secret handling, do not commit real API Key, do not delete history reports, and not investment advice.

## 2026-07-05 Production Readiness V48 gate

- Added `src/services/production_readiness.py`, admin endpoint `GET /api/v1/platform/admin/production-readiness`, and AdminPage production readiness panel.
- The preflight is read-only, admin-only, no-AI, secret-redacted, and explicitly reports `launch_decision=blocked` until external public-launch approvals are completed.
- Blocking checks include real payment, production domain, HTTPS/WAF, data-source commercial license, legal terms, privacy policy, monitoring, and backup/restore proof.
- Added `tests/test_platform_production_readiness_v48.py` and `scripts/verify_platform_production_readiness_v48.py`; the verifier prints `DSA_PLATFORM_PRODUCTION_READINESS_V48_OK` only when required local checks pass.
- V48 remains local-only. It is not public launch approval, not real payment, not production deployment, not legal approval, not data-source license approval, do not commit real API Key, and not investment advice.

## 2026-07-05 Billing Provider Boundary V49 gate

- Added sanitized provider-readiness helpers in `src/billing/payment_provider.py` for disabled, sandbox, unsupported, and Stripe-like real-provider boundary states.
- `/api/v1/billing/checkout` now fails closed with `billing_provider_not_ready` when a real provider is missing required config, and `billing_provider_adapter_not_implemented` when placeholder config exists but no live adapter is implemented.
- `/api/v1/billing/account` returns sanitized `provider_readiness` metadata without exposing secret values.
- Production readiness now reuses provider readiness so real payment remains blocked until config, adapter, merchant, webhook, reconciliation, refund, invoice, and rollback approval exist.
- Added `tests/test_billing_provider_boundary_v49.py` and `scripts/verify_platform_billing_provider_boundary_v49.py`; the verifier prints `DSA_PLATFORM_BILLING_PROVIDER_BOUNDARY_V49_OK` only when required local checks pass.
- V49 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-05 Production Env Gates V50 gate

- `docs/superpowers/platform-production-env.example` now explicitly lists production approval gates for real payment, webhook, domain, HTTPS, WAF, market-data license, legal terms, privacy policy, monitoring, and backup/restore, all defaulting to `false`.
- Stripe-like provider placeholders are present but blank, so the template cannot be mistaken for working payment credentials.
- `scripts/verify_platform_v2_readiness.py` and `scripts/verify_platform_release_candidate_package.py` now require those safe gate defaults.
- Added `tests/test_platform_production_env_gates_v50.py` and `scripts/verify_platform_production_env_gates_v50.py`; the verifier prints `DSA_PLATFORM_PRODUCTION_ENV_GATES_V50_OK` only when required local checks pass.
- V50 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-05 Backup Restore Drill V51 gate

- Added `src/services/platform_backup.py` with a non-destructive SQLite backup/restore dry-run that creates separate backup and restored copies.
- Added `scripts/run_platform_backup_restore_dry_run.py` for operator dry-runs; it requires a database path and defaults output to timestamped `local/backups/dry-runs/...`.
- The dry-run reports integrity checks, file hashes, row-count comparison, `source_unchanged`, `destructive=false`, and `ai_used=false`.
- Added `tests/test_platform_backup_restore_drill_v51.py` and `scripts/verify_platform_backup_restore_drill_v51.py`; the verifier prints `DSA_PLATFORM_BACKUP_RESTORE_DRILL_V51_OK` only when required local checks pass on temporary databases.
- V51 remains local-only. It is not public launch approval, not production backup approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-05 Ops Health V52 gate

- Added `src/services/platform_ops_health.py` and admin endpoint `GET /api/v1/platform/admin/ops-health`.
- Ops health reports database reachability, safe config flags, billing provider readiness, backup runner/verifier availability, and production readiness verifier availability.
- The endpoint is admin-only, read-only, no-AI, no live market-data, and no payment processing.
- Payloads avoid database absolute paths and do not expose API keys, webhook secrets, or tokens.
- Added `tests/test_platform_ops_health_v52.py` and `scripts/verify_platform_ops_health_v52.py`; the verifier prints `DSA_PLATFORM_OPS_HEALTH_V52_OK` only when required local checks pass.
- V52 remains local-only. It is not public launch approval, not production monitoring approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-05 Ops Health Panel V53 gate

- AdminPage now loads `adminOpsHealth()` alongside other admin snapshots and shows an `Ops health` panel.
- The panel shows overall status, total/OK/degraded/critical counts, category chips, and degraded check summaries.
- Frontend API/tests now cover camelCase mapping for `/api/v1/platform/admin/ops-health`.
- Added `scripts/verify_platform_ops_health_panel_v53.py`; the verifier prints `DSA_PLATFORM_OPS_HEALTH_PANEL_V53_OK` only when required local UI/API checks pass.
- V53 remains local-only. It is not public launch approval, not production monitoring approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-06 Local User Acceptance V54 gate

- Anonymous users can continue using `GET /api/v1/stocks/{code}/snapshot` without platform login; no-AI snapshots do not call `AnalysisService`.
- The free no-AI report remains rich enough for local user acceptance: primary summary, mini trend chart, signal score, information digest, market lane, free insights, peer comparison, watch points, product brief, quote details, technical details, and company profile.
- Hong Kong quick snapshots now use the latest historical close as a clearly marked fallback when realtime quote is unavailable, so `00700.HK` can still show a display price without invoking AI.
- Added `tests/test_platform_local_user_acceptance_v54.py` and `scripts/verify_platform_local_user_acceptance_v54.py`; the verifier prints `DSA_PLATFORM_LOCAL_USER_ACCEPTANCE_V54_OK` only when required local checks pass.
- V54 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-06 Local Product Experience V55 gate

- Anonymous visitors now see a guest-first query entry before login, with one-click examples for `AAPL`, `600519`, `00700.HK`, and `BTC-USD`.
- Free no-AI snapshots now include an `intelligence.retention_brief` payload built from deterministic quote, indicator, route, and profile data. It does not call AI or public search.
- HomePage renders `basic-query-retention-brief` with a readable headline, why-it-matters context, support/resistance framing, next steps, a soft upgrade hint, and the `not investment advice` boundary.
- After a guest query, HomePage shows `guest-conversion-guide`: login is optional, the snapshot remains visible, and registration is positioned as saving history, watchlist, and weekly quota state.
- Added `tests/test_platform_local_product_experience_v55.py` and `scripts/verify_platform_local_product_experience_v55.py`; the verifier prints `DSA_PLATFORM_LOCAL_PRODUCT_EXPERIENCE_V55_OK` only when required local checks pass.
- V55 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-06 Local User Retention V56 gate

- A guest can run an `AAPL` no-AI quick snapshot first, then register or log in without losing the current snapshot.
- Signed-in ordinary users can save the current no-AI snapshot to private platform history through `/api/v1/platform/history/snapshot`; AI-used payloads are rejected and history remains scoped by `platform_user_id`.
- The current snapshot panel now offers `Save to history`, `Add to watchlist`, BYOK/platform/local mode switching, and logout without leaving the result view.
- The snapshot retention panel shows free no-AI quota, platform API AI quota, BYOK quota/readiness, local-model quota/capacity, and the `not investment advice` boundary without exposing plaintext keys.
- Playwright mock E2E covers guest AAPL query, registration, save history, add watchlist, logout, login, and saved history/watchlist visibility.
- Added `tests/test_platform_local_user_retention_v56.py` and `scripts/verify_platform_local_user_retention_v56.py`; the verifier prints `DSA_PLATFORM_LOCAL_USER_RETENTION_V56_OK` only when required local checks pass.
- V56 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-06 Local News And K-Line Forecast Lab V57 gate

- Free no-AI snapshots now include `intelligence.news_center`, a deterministic local information center for news, announcements, financials, sector context, and data-quality lanes.
- Free no-AI snapshots now include `intelligence.kline_forecast`, a Kronos-ready K-line forecast lab preview built from quote, moving averages, trend, and volume-price signals.
- The V57 forecast lab does not run Kronos inference, does not call AI, and does not use public search; it exposes `kronos_model_used=false`, `ai_used=false`, and `public_search_used=false`.
- HomePage renders `basic-query-news-center`, `basic-query-kline-forecast-lab`, and `basic-query-premium-feature-ladder` so ordinary users can see richer free value and the upgrade boundary.
- Added `tests/test_platform_local_news_kline_v57.py` and `scripts/verify_platform_local_news_kline_v57.py`; the verifier prints `DSA_PLATFORM_LOCAL_NEWS_KLINE_V57_OK` only when required local checks pass.
- V57 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-06 Kronos Sandbox V58 gate

- Added `src/services/kronos_forecast_service.py`, a local Kronos sandbox adapter with dependency probing, cache, concurrency/timeout boundary, JSONL forecast records, and lightweight record-based backtest summary.
- Added `GET /api/v1/stocks/{code}/kronos-forecast`. Anonymous users can view model readiness and fallback output; `require_model=true` requires login and a pro/premium/enterprise/admin boundary.
- HomePage now renders `basic-query-kronos-sandbox`, `basic-query-kronos-run`, `basic-query-kronos-live-result`, `basic-query-kronos-dependency-status`, and `basic-query-kronos-backtest-summary` so users can distinguish a real Kronos run from the local rules fallback.
- Current local environment lacks required Kronos runtime dependencies, so the honest expected status is `model_unavailable` / `kronos_model_used=false` unless the operator later installs and enables Kronos with `KRONOS_ENABLED=true`.
- Added `tests/test_kronos_forecast_service_v58.py`, `tests/test_kronos_forecast_api_v58.py`, `tests/test_platform_kronos_sandbox_v58.py`, and `scripts/verify_platform_kronos_sandbox_v58.py`; the verifier prints `DSA_PLATFORM_KRONOS_SANDBOX_V58_OK` only when required local checks pass.
- V58 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

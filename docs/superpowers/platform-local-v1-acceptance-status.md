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
- The local Kronos runtime has now been installed on this workstation: `local/kronos`, `torch 2.11.0+cu128`, `einops`, `safetensors`, and Hugging Face model cache are available. When 8018 is started with `KRONOS_ENABLED=true`, `KRONOS_MODEL_ID=NeoQuasar/Kronos-mini`, `KRONOS_TOKENIZER_ID=NeoQuasar/Kronos-Tokenizer-2k`, and `KRONOS_REPO_PATH=local/kronos`, the live endpoint can honestly return `model_ready` / `kronos_model_used=true`. If those runtime flags are disabled or dependencies are missing, it must still show `model_unavailable` or `model_disabled` instead of faking a model run.
- Added `tests/test_kronos_forecast_service_v58.py`, `tests/test_kronos_forecast_api_v58.py`, `tests/test_platform_kronos_sandbox_v58.py`, and `scripts/verify_platform_kronos_sandbox_v58.py`; the verifier prints `DSA_PLATFORM_KRONOS_SANDBOX_V58_OK` only when required local checks pass.
- V58 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-07 A-Stock-Data UI V61 gate

- A-share quick snapshots now accept `a_share_source_mode=poc|a_stock_data|off` from the public no-AI snapshot endpoint.
- HomePage renders an A-share source control inside the A-share enrichment card, showing selected mode, cache diagnostics, local repository revision, and rate-limit count.
- Users can switch to the configured `a-stock-data` adapter and run 600519/000001 probes from the same card; probes remain refreshed no-AI snapshots.
- Frontend API maps `aShareSourceMode` to `a_share_source_mode`; HomePage tests cover the switch and probes.
- Added `tests/test_platform_a_stock_data_ui_v61.py` and `scripts/verify_platform_a_stock_data_ui_v61.py`; the verifier prints `DSA_PLATFORM_A_STOCK_DATA_UI_V61_OK` only when required local checks pass.
- V61 remains local-only. It is not public launch approval, not real payment, not production deployment, not market-data licensing approval, do not commit real API Key, and not investment advice.

## 2026-07-08 Free Peer Reference Quotes V72 gate

- Free no-AI comparison targets now can include lightweight `reference_quote` data: price, change percent, freshness, source, and availability status.
- Peer comparison rows reuse the same `reference_quote` payload so the free comparison table shows concrete reference prices instead of only route-based hints.
- Reference quote fetching uses cache and a short timeout; missing reference quotes degrade to unavailable and do not block the main stock snapshot.
- When the primary platform reference quote source returns empty, the free lane can use a no-key Yahoo chart fallback for public benchmark references.
- HomePage Chinese mode now shows `参照行情`, `参照价`, and `涨跌幅`; free mode displays available public/local reference quotes while premium/API mode can later improve source quality and freshness.
- Added `tests/test_platform_free_peer_quotes_v72.py` and `scripts/verify_platform_free_peer_quotes_v72.py`; the verifier prints `DSA_PLATFORM_FREE_PEER_QUOTES_V72_OK` only when required local checks pass.
- V72 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-08 V73 Free Broker Conversion Acceptance

- HomePage now renders `basic-query-broker-cockpit` directly after the main result summary, before the longer commercial journey and deeper detail modules.
- The free no-AI result first screen now frames the query as `经纪人首屏研判`: `现在值不值得继续看`, `结论`, `证据链`, `风险边界`, and `升级后解决什么`.
- Free and premium users still see the same visible research structure. The free copy says `免费版先给完整研究结构`; the premium copy says `高级版换实时 API、来源链接和模型深度`.
- The cockpit is derived from existing no-AI snapshot data and does not introduce AI calls, public search, real payment, production deployment, or real API Key handling.
- Added `tests/test_platform_free_broker_conversion_v73.py` and `scripts/verify_platform_free_broker_conversion_v73.py`; the verifier prints `DSA_PLATFORM_FREE_BROKER_CONVERSION_V73_OK` only when required local checks pass.
- V73 remains local-only. It is not public launch approval, not real payment, not production deployment, do not commit real API Key, and not investment advice.

## 2026-07-11 V99 Watchlist Event Radar Acceptance

- Signed-in platform users can build a private daily radar from their own A-share, US, Hong Kong, and crypto watchlist symbols.
- The radar returns price movement, MA5/MA20, 5/20-day changes, volume versus MA5, signal score, freshness, event priority, and suggested observation alerts without invoking AI.
- Only traceable persisted intelligence rows can appear as source updates. Missing feeds degrade to `source_unavailable` or `no_traceable_source` without exposing provider exceptions.
- Free and paid users see the same radar layout. Free processes 10 symbols per review and paid plans process 50; excess watchlist rows remain stored.
- Backend V17/V18/V99 compatibility tests and V99 endpoint isolation tests pass. Frontend API, component, HomePage, lint, build, verifier, and browser evidence are required before final acceptance.
- The verifier prints `DSA_PLATFORM_WATCHLIST_EVENT_RADAR_V99_OK` only after required local checks pass.
- V99 remains local-only. It is not public launch approval, real payment, production deployment, production key handling, or investment advice.

## 2026-07-11 V100 Private Watchlist Alert Loop Acceptance

- Signed-in users can run and save a private daily watchlist review, read their recent review timeline, and manage only their own alert rules.
- Free users receive 3 enabled private alert slots and paid plans receive 50, while both plans keep the same visible workflow and information structure.
- Price movement, volume movement, source update, data quality, and true MA20 side-crossing rules are supported. The first saved run establishes a baseline and does not fake a crossing.
- Source alerts require a traceable persisted HTTP(S) link. Public search, live feed ingestion, and AI quota use remain disabled in this loop.
- Backend ownership, limit, baseline, trigger, and endpoint tests pass; frontend Chinese/English, save/delete, timeline, full regression, lint, and build checks pass.
- Private browser state accepts a response only when the session generation still matches and, where the response carries ownership, its `userId` also matches; logout or user switching invalidates in-flight account, API-key, watchlist, history, rule, and radar responses.
- Current-plan caps are reapplied on list and execution, source URLs are compared with the prior run, rule deletion is soft-disable, non-finite values are rejected, and all V100 writes retain CSRF plus write-rate-limit coverage.
- Same-user radar runs, rule saves, and rule disables are serialized in the local process, and bounded A-share/HK symbol variants are covered when matching already persisted traceable sources.
- Failed logout confirmation is contained locally: private UI state and busy flags are cleared, the raw error is not exposed, and the active interface language receives a refresh/session warning.
- The verifier prints `DSA_PLATFORM_WATCHLIST_ALERT_LOOP_V100_OK` only after its required local checks pass.
- V100 remains local-only. It is not public launch approval, real payment, production deployment, production key handling, market-data licensing approval, or investment advice.

## 2026-07-11 V101 Free Historical Trend Research Acceptance

- Guest quick analysis now lazy-loads a free historical trend panel backed by the existing public daily-history endpoint; lookup mode remains lightweight and does not load the panel.
- Users can switch among 30, 90, 180, and 365-day ranges and inspect actual close, MA5, MA20, volume, range return, high/low, maximum drawdown, source, and deterministic next-check conditions.
- The panel does not require login, call AI, consume platform/BYOK/local-model quota, or enable public search.
- Chinese and English loading, usable-data, empty-data, and failure states are covered; raw provider errors are not rendered.
- Existing quick-snapshot close points render immediately while full OHLCV history loads; if the secondary history source fails, the close-only chart remains visible with a degradation label.
- The verifier prints `DSA_PLATFORM_FREE_KLINE_RESEARCH_V101_OK` only after API, component, HomePage integration, and production-build checks pass.
- V101 remains local-only and uses public/local market data that may be delayed or incomplete. It is not production market-data licensing approval or investment advice.

## 2026-07-11 V102 A-share Free Query Speed Acceptance

- The five optional A-share enrichment channels now run concurrently instead of serially; the default total enrichment wait is bounded to 1.5 seconds.
- Deterministic tests prove parallel completion, total-budget degradation, immediate timeout-cache reuse, cross-request default-adapter cache reuse, stable channel order, and no-AI/no-public-search boundaries.
- A real local service-layer probe for 600519 measured about 1.5 seconds for the first enrichment and about 0.001 seconds for the immediate repeated enrichment with five cache hits.
- After restarting 8018 with the final code, a direct HTTP cold request measured 4.405 seconds while public quote/history sources were probed; the immediate repeat measured 0.807 seconds after source-health cooldown and cache reuse. The response kept stale quote/history warnings visible.
- Fresh browser acceptance on `/?dsa_v102_cold_acceptance=1` measured 1.604 seconds for the free 600519 quote view and 0.281 seconds to expand the complete free research board. The page visibly retained A-share enrichment, the historical K-line research board, no-AI status, and the untouched `5/5` platform-API trial quota, with no load/service/run-failure banner.
- Optional A-share peer/reference quotes now honor source-health cooldown, so an already cooling market source no longer adds another bounded timeout to repeated free snapshots.
- Slow or unavailable public sources remain channel-level degradation. Quote/history evidence and completed channels are not discarded, and cached timeout results are not labeled fresh.
- The verifier prints `DSA_PLATFORM_A_SHARE_FREE_QUERY_SPEED_V102_OK` only after required-file, source-contract, git-visibility, and focused regression checks pass.
- V102 remains local-only. It does not approve real payment, production deployment, production keys, market-data licensing, or investment advice.

## 2026-07-11 V103 Free Daily Research Cockpit Acceptance

- The existing authenticated V99/V100 watchlist review now adds a deterministic daily research digest without adding another live-data or AI request.
- Each visible symbol is classified into strong confirmation, risk review, or wait for confirmation and includes structured evidence, next-watch, invalidation, priority, and data-confidence fields.
- Low-confidence, stale, warning-bearing, or unavailable data is forced into risk review and cannot be presented as strong confirmation.
- HomePage renders a bilingual three-group cockpit before the detailed event radar, with fresh/cached/stale/unavailable counts and a symbol drill-down that does not automatically spend API quota.
- Live browser acceptance on 8018 processed four private watchlist symbols in about 2.146 seconds for the first Chinese review and about 0.291 seconds for the cached English review. AAPL drill-down completed in about 0.289 seconds while the platform API trial remained `5/5`.
- Chinese and English both rendered all three group headings, confidence labels, data-health counts, quota boundary, and safety copy. Browser error logs and load/service/run-failure banners were all zero.
- The cockpit displays the current weekly platform API trial balance and keeps the existing explicit trial action on the stock page as the only consumption point.
- Focused V103 verification covers the new backend contract plus existing V99/V100 isolation, alert, and history behavior, and covers API mapping, Chinese/English rendering, HomePage integration, and symbol navigation in the frontend.
- The verifier prints `DSA_PLATFORM_FREE_DAILY_RESEARCH_COCKPIT_V103_OK` only after required files, source contract, Git visibility, backend tests, and frontend tests pass.
- V103 remains local-only, no-AI by default, non-destructive, and informational analysis only. It is not production launch approval, real payment, production key handling, market-data licensing approval, or investment advice.
## 2026-07-11 V104 Market Data Screening And Condition Alerts Acceptance

- AlphaSift candidates now include a deterministic `screening_brief` with matched condition codes, observed metrics, source freshness, data completeness, information flags, observation codes, condition-exit codes, and explicit AI-use provenance.
- The screening result surface uses neutral data cards. Provider narratives, raw recommendation fields, target prices, return forecasts, and buy/sell instructions are not rendered in the V104 card contract.
- Users can compare up to five results. Logged-in users can add a result to their private watchlist and save an existing V100 condition-alert rule; guests receive a login-required state without losing the public screening page.
- Anonymous users can call the information-only AlphaSift status, strategy, hotspot, task submission, and task status paths. AlphaSift install remains protected. Public screening passes `use_llm=false` so it cannot consume a model API by default.
- The sidebar keeps `Market screening` / `市场筛选` visible even when the local AlphaSift engine is disabled, so the page can explain availability and degraded state instead of disappearing.
- Chinese and English V104 data cards, comparison labels, alert labels, route labels, and information-boundary copy are covered by focused tests.
- `scripts/verify_platform_market_screening_alerts_v104.py` prints `DSA_PLATFORM_MARKET_SCREENING_ALERTS_V104_OK` only after required-file, source-contract, information-boundary, Git-visibility, backend, and frontend checks pass.
- V104 remains local-only. It does not enable real payment, production keys, public deployment, or production market-data licensing, and it is not investment advice.
- Anonymous local users can run the public market-data screen without a platform login or an AI API key; the default path explicitly uses `use_llm=false`.
- The live task reports staged full-market snapshot/filter/coverage progress instead of remaining at a static 20 percent state, and completed results identify AI as unused rather than incorrectly reporting an LLM degradation.
- Built-in strategy names and descriptions are presented as neutral data filters in Chinese and English; entry-opportunity and trading-signal wording is not rendered in the V104 strategy cards.
- The complete primary screening surface now follows the selected locale, including themes, filter settings, progress, result metadata, comparison, alerts, and boundary copy; a focused page test protects the English mode from mixed Chinese UI labels.
- The unreachable legacy result table containing operation-signal and LLM-judgment fields was removed from `StockScreeningPage.tsx`; V104 has a single neutral result renderer.

## 2026-07-11 V105 Fast Useful Market Screening Acceptance

- Recent full-market snapshots are preferred for repeat anonymous/free screening; trading-session TTL is short and off-hours TTL is longer.
- Users can explicitly force a slower source refresh.
- Responses expose cache use, cached timestamp, age, TTL, forced-refresh state, and elapsed milliseconds.
- Cards expose factual valuation, liquidity, trading-value, and market-cap fields when available.
- Results support local sorting and secondary filters without another request or AI usage.
- The recent-snapshot fast path skips blocking per-symbol enrichment; opening a result remains the explicit path for detailed company data.
- Live acceptance on `http://127.0.0.1:8018/screening` reduced a cached repeat request from about 28.6 seconds before the fast-path correction to 55 milliseconds at the API client and 47 milliseconds in the service; the browser displayed the same cached run as 0.1 seconds.
- Anonymous Chinese and English browser acceptance passed with localized sorting/filter controls, cache provenance, visible no-AI status, information-only copy, and no browser console errors.
- AlphaSift feature enablement now uses a narrow platform-admin endpoint instead of the broad system-config write route. Ordinary users see the disabled state without a misleading enable button; once enabled, anonymous and free users can still run no-AI screening.
- Weekend snapshots remain reusable for 72 hours and weekday off-hours for 18 hours, while the trading-session TTL stays at 5 minutes. Slow forced refreshes expose elapsed-time progress and remain below the completion threshold until results exist.
- `scripts/verify_platform_fast_useful_screening_v105.py` prints `DSA_PLATFORM_FAST_USEFUL_SCREENING_V105_OK` only after static, backend, and frontend checks pass.

## 2026-07-11 V106 Financial Research Workflows Acceptance

- The official `anthropics/financial-services` source is installed as an ignored shallow checkout at accepted commit `4aa51ed3d379731f8f9beff498d749580372699c` under Apache-2.0.
- DSA recognizes only company snapshot, earnings review, sector overview, and catalyst-calendar references. It never imports or executes the external agents, commands, scripts, or MCP connectors.
- `GET /api/v1/stocks/{stock_code}/research-workflows` is public and deterministic. It reuses the current DSA no-AI stock snapshot and supports an explicit snapshot refresh without model or public-search usage.
- `/research` provides a bilingual anonymous research center with factual values, source/freshness labels, missing-data reasons, source commit, license, disabled-connector state, and external-code-not-executed state.
- Live browser acceptance on `8018` covered AAPL and `600519.SH`: growth percentages render without double scaling, Chinese mode hides internal English source/status tokens, and switching to English preserves the current symbol and result without an extra refetch.
- Missing provider facts produce a partial workflow instead of fabricated content. Every response and page keeps the information-and-data-only boundary.
- Review hardening keeps placeholder event lanes `partial`, attaches currency/unit metadata to facts, rejects an unaccepted external commit, and uses an exact anonymous GET route match.
- The external checkout is not committed into the DSA Git history and is not evidence of market-data licensing, production connector approval, or public-launch readiness.

## 2026-07-11 V107 Ollama Local AI Retention Acceptance

- Local Ollama 0.24.0 is reachable and both configured fast/deep model lanes report ready through the secret-free status API.
- A direct LiteLLM fast-model probe returned through the Ollama provider, and a complete AAPL local analysis finished with `model_used` set to the local Ollama model.
- The full local result returns `仅供信息观察`; entry, stop-loss, take-profit and target fields are empty. The same boundary is applied before database persistence.
- Browser regression generated a new AAPL report whose card reads `仅供信息观察 50`, whose summary contains no actionable levels, and whose model is `ollama/qwen3-vl:8b-instruct`.
- Two earlier acceptance reports were preserved in storage; a read-only compatibility mask now renders all three Ollama history cards and details with the same information-only boundary.
- Anonymous local-AI execution is rejected, while the readiness endpoint remains public. Unavailable preflight returns a stable 503 reason without charging `ai_local`.
- Busy or timed-out synchronous local execution returns a stable local-model reason and releases its uniquely referenced quota reservation when no report was produced.
- The HomePage displays bilingual local readiness, fast/deep models, remaining weekly quota and a dedicated local-AI detailed-read button while preserving the no-AI quick-analysis path.
- Free and paid local usage remain separate from platform API and BYOK usage. Current limits retain the existing free 50 / paid 500 weekly local bucket policy.
- Live quota regression showed platform API trial `5/5` and local-model quota `46/50` after four Ollama analyses; the fourth balance updated without a page reload, proving the local lane no longer double-charges the platform bucket and the UI refreshes immediately.
- Acceptance marker: `DSA_PLATFORM_OLLAMA_LOCAL_RETENTION_V107_OK`.
- V107 remains local-only and is not production-launch, real-payment, market-data-license or investment-advice approval.

## V112 本地状态（2026-07-12）

- 本地代码：API 加油包沙箱、统一模型目录、三步 BYOK、用户 Ollama 配对/令牌/加密任务和双平台构建门禁已纳入本地验收。
- Windows 本地开发验收：连接器发现 9 个 Ollama 模型，统一目录展示 9 个本机选项；AAPL 实际分析 8.80 秒返回 200，`ai_local` 公平使用额度从 500 降为 499，输出保持“仅供信息观察”。
- Windows 开发包：`DSA-Local-Connector-Windows-x64.exe` 已由 PyInstaller 构建，大小 19,647,339 bytes，SHA-256 `1950C4356ABB42D404673C55757AB521920F80764348063B1300C92022C9AE7F`；隐藏启动烟雾通过，`/downloads/DSA-Local-Connector-Windows-x64.exe` 返回 200。
- 安全边界：明文 Key、设备 token、prompt 和模型结果不得写入审计或日志；BYOK 白名单默认空并 fail closed。
- 本地已验：`REAL_USER_OLLAMA_WINDOWS_LOCAL_DEV_VERIFIED`。明确未验：`REAL_OPENAI_CLAUDE_BYOK_NOT_VERIFIED`、`REAL_USER_OLLAMA_MACOS_NOT_VERIFIED`、`LOCAL_CONNECTOR_SIGNING_NOT_READY`。
- 发布边界：真实支付、生产密钥、Windows 正式签名、Apple Developer ID/notarization 和 macOS Intel/Apple Silicon 真机证据仍为阻塞项，不得宣称公网可上线。
- 合规边界：只提供资讯和数据，不提供投资建议、买卖指令、仓位、目标价或收益承诺。

## V113 本地市场工作台状态（2026-07-12）

- 新增 `/market` 原生市场工作台，游客可查看 A 股、港股、美股总览、全局搜索、涨跌图、变化列表和来源状态；登录后可保存自选和客观价格条件提醒。
- 后端公开 `overview`、`search`、`symbol`，私人 `daily-brief` 继续要求平台登录；所有 V113 响应保持 `ai_used=false` 和 `informational_only=true`。
- 性能根因从完整快照链路收敛为报价卡片；总览使用有界并行和 2.5 秒整体截止时间。真实冷启动为 A 股 2.06 秒（4 条）、港股 2.01 秒（4 条）、美股 0.31 秒（5 条），缓存请求约毫秒级。
- 浏览器验收发现并修复前端漏写 `/api/v1`、旧响应缺字段导致整页崩溃、跨市场列表残留和 A 股指数代码归一化冲突。最终 A 股 4 行、美股 5 行、港股 4 行，切换后无跨市场残留、无横向溢出、无控制台错误。
- 聚焦后端测试 13 项通过；前端 API/页面测试 7 项通过；lint 与生产构建通过。
- `scripts/verify_platform_market_workspace_v113.py` 输出 `DSA_PLATFORM_MARKET_WORKSPACE_V113_OK markets=cn,hk,us guest=true watchlist=true alerts=true ai_required=false agpl_code_copied=false`。
- OpenStock 仍为产品灵感来源，不作为代码、依赖或运行服务安装。V113 不批准真实支付、生产密钥、公开部署或市场数据授权，也不构成投资建议。

## V115 统一数据中台与来源仲裁状态（2026-07-12）

- 单股基础查询现在返回 `canonical_data`，记录行情、历史 K 线和公司资料的选中来源、新鲜度、观测时间、缓存状态和字段级来源。
- 来源仲裁使用“新鲜度、市场来源优先级、观测时间”顺序；冲突价格不取平均值。
- 资讯、公告和事件记录支持来源编号或规范化 URL 去重，并记录输入数、输出数和移除数。
- 免费版“数据可信度”区域显示统一事实快照、来源类型、冲突数量和去重数量，中英文均有固定文案。
- Kronos 和 AI 继续属于派生信息层，不得覆盖行情、财务或公告事实。
- `scripts/verify_platform_unified_market_data_v115.py` 通过时输出 `DSA_PLATFORM_UNIFIED_MARKET_DATA_V115_OK canonical_snapshot=true source_arbitration=true deduplication=true no_averaging=true ai_required=false`。
- V115 仍是本地功能闭环，不代表真实支付、公开部署、生产密钥或市场数据授权获批；所有内容仅为资讯和数据，不构成投资建议。

## V116 首页市场速览与精确到价提醒状态（2026-07-13）

- 首页新增公开三市场聚合，固定按 A股、港股、美股顺序返回；单市场失败不会清空另外两个市场。
- 精确到价规则复用 V100 私有提醒表，支持首次基线、真实穿越、stale 不触发、同股单轮去重和 A/B 用户隔离。
- 站内提醒事件支持私有列表、单条已读和全部已读；全站页头提醒铃每 60 秒重新确认平台会话。
- 游客到价提醒草稿保存 30 分钟，注册后恢复为待确认表单，不会静默创建提醒。
- `scripts/verify_platform_public_market_price_alerts_v116.py` 通过时输出 `DSA_PLATFORM_PUBLIC_MARKET_PRICE_ALERTS_V116_OK markets=cn,hk,us guest_home=true exact_price_alerts=true background_monitor=true private_events=true ai_required=false realtime_claim=false`。
- 本状态仅代表本地验收，不代表市场数据授权、生产部署、原生 APP、推送通道、支付或法律审批；内容不构成投资建议。

## V117 六项功能体验与 Ollama 验收状态（2026-07-13）

- 六项 DSA 产品能力统一验收：Kronos、a-stock-data A 股增强、AlphaSift、Financial Services、市场工作台和市场脉搏/自选简报。
- 本地 Ollama 快速模型分别完成 AAPL 与 `600519.SH` 信息分析；成功结果不含买卖动作或目标价，继续使用独立 `ai_local` 额度。
- Kronos RTX 5090 探针继续真实运行；模型状态、行情源降级和端到端耗时分别展示。
- 港股和美股详情获得公开行情/历史兜底；市场总览与股票详情分层加载，直达链接不再被旧市场请求覆盖。
- AlphaSift 筛选结果支持当前浏览器会话恢复，过期快照快速路径必须显式配置并标记 `snapshot_cache_stale`。
- 中文和英文页面统一格式化来源、状态、时间、数值和警告；游客首页不再建立需要登录的任务事件流。
- `scripts/verify_platform_six_feature_experience_v117.py` 通过时输出 `DSA_PLATFORM_SIX_FEATURE_EXPERIENCE_V117_OK features=6 ollama=true markets=cn,hk,us guest_data=true investment_advice=false`。
- 本状态仍是本地功能验收，不代表真实支付、生产密钥、公开部署、市场数据商业授权或法律审批。

## V118 财经首页信息架构状态（2026-07-13）

- 首页首屏改为公开 A股、港股、美股市场焦点，展示主要指数、关注股票、最新可用价格、涨跌、来源状态、更新时间和公开市场快讯。
- 正式资讯存在时展示发布方、时间和原始链接；资讯源降级时只显示明确标注的行情动态，不伪造新闻。
- 游客注册表单默认折叠；已登录用户只看到邮箱、套餐、每周额度、个人工作台、账户与模型入口和退出。
- 自选、今日复盘和提醒保留在按需展开的个人工作台；模型选择迁入账户页并继续使用 `dsa.modelOptionId`。
- 首页自动加载路径不运行平台 API、BYOK、Ollama 或 Kronos；这些能力只在用户主动查询后运行。
- `scripts/verify_platform_public_home_experience_v118.py` 通过时输出 `DSA_PLATFORM_PUBLIC_HOME_EXPERIENCE_V118_OK markets=cn,hk,us public_news=true account_clickthrough=true mobile=true api_auto_run=false investment_advice=false`。
- 本状态仅代表本地功能验收，不代表生产部署、支付、市场数据商业授权或法律审批；所有页面仅提供资讯和数据，不构成投资建议。
- 浏览器实测覆盖桌面和 390x844 手机视口：A股、港股、美股分别显示公开基准指数、关注行情和 5 条来源可追溯资讯，手机无横向溢出，控制台无警告或错误。
- 首次 `/api/v1/market-workspace/home` 实测约 2.48 秒，三地各返回 6 条公开资讯且 `ai_used=false`；主动查询 AAPL 后才进入个股工作区，首页自动加载未运行平台 API、BYOK、Ollama 或 Kronos。

## V119 动态市场首页状态（2026-07-14）

- 首页固定股票池已从公开热门区域移除，A 股、港股、美股分别返回全市场活跃榜、涨幅榜和跌幅榜；`attention` 仅作为活跃榜兼容别名。
- A 股新增公开行业热点及领涨标的；港股和美股行业热点在没有可靠公开源时明确降级，不构造假数据。
- A 股和港股榜单来自新浪财经公开排序接口，美股来自 Yahoo Finance 公共 screener；来源状态、观察时间、交易阶段与缓存状态随数据返回。
- 榜单服务使用有界并发、网络硬超时、120 秒热缓存和 30 分钟最近成功缓存；源失败时展示 stale 或 unavailable，禁止回退固定股票。
- 本地公开网络探针：三市场冷加载约 1.82 秒，热缓存约 0.0004 秒；三市场均返回活跃、涨幅和跌幅数据，A 股同时返回行业热点。
- 首页自动加载保持 `ai_used=false`、`informational_only=true`，不消耗平台 API、BYOK、Ollama 或 Kronos 额度；点击股票后进入现有免费查询。
- `scripts/verify_platform_dynamic_market_home_v119.py` 通过时输出 `DSA_PLATFORM_DYNAMIC_MARKET_HOME_V119_OK markets=cn,hk,us rankings=active,gainers,losers sectors=cn public_data=true ai_used=false fixed_pool=false investment_advice=false`。
- 本状态仅代表本地功能验收，不代表生产部署、支付、市场数据商业授权或法律审批；所有页面只提供资讯和数据，不构成投资建议。

## V120 平台客服中心状态（2026-07-14）

- 新增独立文本工单与消息表，不与 LukaAI 共享数据库、会话或后台账号。
- 注册用户可在 `/support` 创建、查看、回复和关闭自己的工单；跨用户访问统一返回不存在。
- 管理员可在 `/admin` 查看客服队列、读取详情、人工回复和切换待处理、处理中、已关闭状态。
- 用户与管理员未读状态独立维护；审计只记录工单 ID、分类和状态，不记录消息正文。
- 所有写接口复用平台 CSRF 和独立限流桶；关闭工单禁止继续回复，管理员可显式重新打开。
- V120 不启用 AI 自动回复、知识库、附件、外部客服渠道或投资建议能力。
- `scripts/verify_platform_support_center_v120.py` 通过时输出 `DSA_PLATFORM_SUPPORT_CENTER_V120_OK user_loop=true admin_queue=true ownership_isolated=true csrf=true rate_limit=true ai_reply=false attachments=false investment_advice=false`。
- 本状态仅代表本地功能验收，不代表生产部署、真实支付、生产密钥、跨产品数据同步或法律审批。

## V121 免费市场股票数据预览状态（2026-07-14）

- 动态首页全市场榜单新增独立“数据详情”入口，游客点击后复用公开 `market-workspace/symbol` 数据，不要求登录。
- 预览展示行情区间、成交量额、均线、近期变化、量能对比、公司行业、市值、历史收盘曲线、来源状态和更新时间。
- 首页加载阶段不预取股票详情；请求失败时榜单保持可用，用户可重试或关闭；切换市场或榜单会清理旧详情。
- 点击后立即呈现榜单现价、涨跌、成交额和来源，再异步补充均线、历史曲线与公司资料，降低公开详情冷请求的等待感。
- 数据缺失统一显示“暂不可用”，不伪装为零；客观位置描述不推断未来方向。
- 前端组件和首页集成测试覆盖中文、英文、缺失降级、错误重试、完整查询入口和请求次数。
- 8018 真实浏览器覆盖 A 股中际旭创、港股中芯国际和美股 AAL：三市场均能显示未使用 AI、近期收盘曲线、数据来源和资讯边界；榜单价格与详情补充采用不同时间口径时，首要价格和涨跌仍以用户所见榜单为准。
- `390x844` 手机视口中文和英文详情均无横向溢出；英文模式显示 `Public data preview`、`No AI used` 和 `Information and data only`。点击“进入完整查询”实际打开 `/market?symbol=0981.HK`。
- 港股冷详情可能需要约 11 秒，但点击后立即显示榜单价格、涨跌、成交额和来源，不阻塞榜单浏览；错误重试和榜单保留由确定性集成测试覆盖。
- `scripts/verify_platform_free_market_stock_preview_v121.py` 通过时输出 `DSA_PLATFORM_FREE_MARKET_STOCK_PREVIEW_V121_OK guest=true on_demand=true public_data=true ai_used=false bilingual=true mobile=true investment_advice=false`。
- 本状态仅代表本地免费公开数据功能，不代表生产部署、真实支付、生产密钥、市场数据商业授权或法律审批；所有内容只提供资讯和数据，不构成投资建议。

## V122 客服站内通知状态（2026-07-14）

- 用户侧“客服”角标显示未读客服回复数，管理员侧“运营”角标显示未关闭工单数。
- 摘要 API 已覆盖用户隔离、管理员权限、未读计数、待处理计数和最早等待时间，不返回主题或消息正文。
- 游客不调用客服私有摘要；页面隐藏时不轮询，恢复可见、会话变化或工单操作后立即刷新。
- 桌面和 `390x844` 移动视口浏览器回归覆盖角标显示、读取清除、关闭工单清除和无横向溢出。
- `scripts/verify_platform_support_notifications_v122.py` 通过时输出 `DSA_PLATFORM_SUPPORT_NOTIFICATIONS_V122_OK user_badge=true admin_badge=true polling=visible_only summary_redacted=true ai_reply=false external_notifications=false`。
- 本状态仅代表本地人工客服站内通知验收，不代表 AI 回复、外部通知、生产部署、真实支付或生产密钥已批准。

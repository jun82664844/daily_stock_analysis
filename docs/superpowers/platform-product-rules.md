# DSA Platform Product Rules

## Cost Lanes

- Basic query uses market data and deterministic indicators only. It must not call an AI model.
- Query Quality V4 keeps the unified quick entry in the no-AI lane by default. A-share, US equity, HK equity, and crypto spot symbols resolve to explicit market-data lanes before any AI action is offered.
- Quick snapshots may show cached/stale/missing quote or history warnings, but they must not silently fall back to AI or public search.
- Quick AI analysis uses the `ai_quick` quota bucket.
- Quick AI analysis in user-owned API mode uses the `ai_quick_user_key` abuse-control bucket and does not consume platform model cost units.
- Deep AI analysis uses the `ai_deep` quota bucket in platform API mode.
- Deep AI analysis in user-owned API mode uses the `ai_deep_user_key` abuse-control bucket and does not consume platform model cost units.
- Local model mode uses the `ai_local` abuse-control bucket and does not consume platform model cost units.
- Market review is a separate manual operation and uses the `market_review` bucket.

## Plans

- Free users can run basic queries and limited quick AI analysis.
- Free users cannot use platform-key deep analysis unless the plan policy is changed.
- Pro users get higher quick/deep AI limits.
- `premium` is retained as a backward-compatible local alias for the same paid tier as `pro`.
- Enterprise users may have unlimited limits or contract-defined limits.

## User-Owned API Mode

- User API keys are encrypted at rest.
- API key responses only expose provider, optional model, enabled state, timestamps, and masked key.
- Plaintext API keys must not be returned, rendered, logged, or stored in audit metadata.
- User-owned API mode still consumes server-side abuse-control quota in BYOK-specific buckets.
- Audit metadata is recursively redacted before storage, and the admin frontend applies a second rendering-time redaction guard.
- The user account center may save/update provider API keys and models, but it must only render masked key state after save.

## User Account Center

- Ordinary platform users can view their own email, role, plan, base quota, feature quota buckets, masked API key state, and recommended query mode.
- Ordinary platform users must not see the admin navigation entry after the platform session resolves, and backend admin data remains forbidden to non-admin users.
- Account and history views are scoped by `platform_user_id`; users must not see another user's history or admin usage data.

## Public Entry And Admin Boundary

- The ordinary platform-user entry routes (`/`, `/portfolio`, `/chat`, `/account`, and `/usage`) must remain reachable without an admin cookie so users can register, log in, and query locally.
- Anonymous visitors may run the public no-AI quick snapshot path, `GET /api/v1/stocks/{symbol}/snapshot`, so the first stock lookup is not blocked by login.
- Anonymous quick snapshots must remain market-data-only: no AI model call, no AI quota consumption, no BYOK access, no watchlist/history ownership write, and visible degradation warnings when quote or history data is stale or unavailable.
- Account center, private history, watchlist persistence, BYOK keys, quick/deep AI analysis, billing, and admin/operator data still require the appropriate platform session and permission checks.
- Admin/operator routes (`/admin` and `/settings`) require an admin session at the frontend route layer, and backend admin APIs remain protected server-side.
- The admin login page is for operator access only; it must not block the ordinary platform-user query entry.
- Frontend 401 handling must not globally redirect ordinary platform-user API failures to the admin login page; admin login redirect is only for admin-only browser routes.
- Public unauthenticated navigation must not show admin-only entries or admin logout controls.
- Public unauthenticated history initialization may show empty history, but it must not render `Login required` as a page-level error on the ordinary query entry.

## Platform User Watchlist

- Platform-user watchlists are private to each signed-in user and separate from the global `STOCK_LIST` configuration watchlist.
- Watchlist refresh uses the no-AI quick snapshot lane for A-share, US equity, HK equity, and crypto spot symbols, and must not consume AI quota.
- The watchlist board may display price, change percent, route lane, freshness, degradation status, and warning codes, but row actions must reuse the existing quick snapshot path instead of triggering deep/AI analysis.
- The ordinary-user public flow must allow local register/login, account summary, quick query, add-current watchlist, and refresh-watchlist operations without exposing admin navigation or plaintext API keys.

## Query Workspace

- The ordinary-user HomePage may show a local workspace status band for current snapshot, watchlist, historical reports, and AI analysis state.
- The current snapshot segment must represent fresh quick-query state only and must not imply that a historical report has been refreshed.
- The AI segment may show selected platform/BYOK/local mode and BYOK readiness, but quick snapshots must remain no-AI unless the user explicitly runs an AI analysis action.

## Market Refresh

- The default quick snapshot path is cache-first and must remain no-AI.
- Manual current-snapshot refresh uses `snapshot?refresh=true`; it bypasses snapshot cache, updates local market cache after a deterministic quote/history fetch, and must not submit AI analysis.
- Refresh diagnostics must expose `force_refresh`, quote/history cache state, source, freshness, fallback, and source health.
- Refresh failures or unavailable upstream market sources must degrade visibly instead of being presented as complete fresh data.
- Historical AI reports must be visibly labeled as historical output and not current quote data. Refreshing current quote from a historical report must use the no-AI `snapshot?refresh=true` path and must not submit AI analysis.

## History Export

- History export is a local browser download of selected persisted history records.
- Export supports Markdown and JSON bundles and must return `ai_used=false`.
- Ordinary platform users can export only records scoped to their own `platform_user_id`; admin/global local context can use the existing global history scope.
- Export must redact secret-like strings and must not dump raw API keys, bearer tokens, passwords, or raw_result secret metadata.
- Export must not delete, rewrite, refresh, or re-analyze historical reports.
- Exported reports remain informational analysis only and are not investment advice.

## Local Model Mode

- Local model capacity is bounded by `LOCAL_LLM_MAX_CONCURRENT`.
- When capacity is full, requests should receive a clear busy reason instead of silently queueing forever.
- Local model mode is optional and must not affect no-AI basic queries.
- Local model mode is independently accounted in `ai_local`; it remains local V1 infrastructure, not a hosted model SLA.

## Query Quality V4

- A-share quick query uses the A-share market-data lane; US symbols use the US market-data lane; crypto symbols such as `BTC-USD` use the crypto spot market-data lane.
- Quick snapshots expose route metadata, quote freshness, moving averages, volume/price signal, and degradation warnings for stale quote, missing quote, or missing history.
- Deep/AI analysis remains explicit through quick/deep action buttons and continues to consume platform, BYOK, or local-model quota buckets according to the selected mode.
- Public search remains disabled by default unless explicitly configured by an operator; search failures must degrade visibly instead of being presented as complete information.

## Local News And Forecast Lab V57

- Free no-AI snapshots may show a local `news_center` with news, announcements, financials, sector context, and data-quality lanes, but it must remain deterministic and must not call AI, public search, or paid APIs.
- `news_center.public_search_used` must remain `false` unless a future operator-approved source policy explicitly enables public search.
- Free no-AI snapshots may show a `kline_forecast` lab preview built from quote, moving averages, trend, and volume-price signals.
- The V57 K-line forecast lab is Kronos-ready but must expose `kronos_model_used=false` until a real Kronos/local-model adapter, model files, data license boundary, and performance gate are approved.
- The forecast lab is an experimental information view. It must show the `not investment advice` boundary and must not present scenarios as trade instructions.
- Free and premium pages should show the same visible modules in local V1. The product distinction is data channel quality: free mode uses network/local public sources, while premium/API modes can use platform API, user API, approved feeds, or local models for fresher, steadier, deeper output. The copy must not imply real payment or production readiness in local V1.

## Kronos Sandbox V58

- Public visitors may call `GET /api/v1/stocks/{symbol}/kronos-forecast` to see Kronos sandbox readiness, dependency status, local fallback scenarios, forecast points, and a lightweight local record/backtest summary.
- The public sandbox endpoint must remain no-AI and no-public-search when the real Kronos runtime is unavailable or disabled.
- The endpoint must not claim `kronos_model_used=true` unless `KRONOS_ENABLED=true`, required local dependencies are present, and the local Kronos predictor actually returns forecast points.
- `require_model=true` is reserved for real model execution and requires a signed-in pro/premium/enterprise user or admin. Anonymous users may see readiness/fallback status, but they cannot force a real model run.
- Missing `torch`, `einops`, `safetensors`, `huggingface_hub`, or Kronos `model` dependencies must be shown as `model_unavailable` instead of being hidden behind generic failures.
- Kronos forecast records are local JSONL metadata only and must not include API keys, bearer tokens, passwords, webhook secrets, or production credentials.
- HomePage must visually distinguish the static V57 `kline_forecast` rules preview from the V58 live Kronos sandbox check via `basic-query-kronos-*` UI markers.
- V58 remains local-only. It is not a public launch approval, not real payment, not hosted model SLA, and not investment advice.

## User Retention V56

- Guest no-AI quick snapshots may be converted into private user retention only after registration or login; anonymous users must not write history or watchlist ownership data.
- Saving the current snapshot to history is a no-AI local operation and must reject payloads that declare `ai_used=true` or route `ai_required=true`.
- Snapshot-to-history writes must be scoped to the current `platform_user_id`; another ordinary user must not see the saved record.
- Adding the current snapshot to watchlist must use the current snapshot symbol when the search input is empty after login state refresh.
- The current snapshot UI may show free no-AI quota, platform API AI quota, BYOK quota/readiness, and local-model quota/capacity together, but must not expose plaintext API keys, tokens, secrets, or passwords.
- Logout and login should reload private history/watchlist state. Saved records remain informational analysis only and are not investment advice.

## Local V1 Billing Boundary

- Billing routes exist for contract testing.
- `BILLING_ENABLED=false` keeps checkout disabled in local V1.
- Webhooks must reject missing signatures before any provider-specific processing.
- `BILLING_ENABLED=true` with `BILLING_PROVIDER=sandbox` is a local-only mock payment lane. It can create sandbox checkout sessions and process signed test webhooks for a free-to-pro upgrade in tests.
- Sandbox webhook bodies are verified with the local sandbox secret before plan changes. Missing or bad signatures are rejected.
- Local sandbox billing records checkout sessions, billing events, and per-user subscription state for lifecycle testing only.
- Supported local sandbox events are `checkout.created`, `checkout.completed`, `checkout.cancelled`, `checkout.expired`, `payment.failed`, and `subscription.updated`.
- Sandbox webhooks are idempotent by `provider_event_id`; repeated events return an idempotent result and must not duplicate upgrades or usage.
- Completed checkout events may activate the requested local test plan; cancelled, expired, and failed checkout events do not upgrade the user.
- `subscription.updated` may reconcile `free`, `pro`, `premium`, or `enterprise` only inside the sandbox test lane.
- User and admin billing UI must label this as local sandbox/mock payment. Sandbox billing copy must not claim real payment launch readiness; real merchant onboarding, reconciliation, refunds, invoices, and compliance remain V2/no-go items.

## Safety Copy

- Reports are informational analysis only.
- Prices and indicators come from data providers and carry source/freshness metadata.
- Historical reports are historical snapshots and should not be confused with fresh queries.

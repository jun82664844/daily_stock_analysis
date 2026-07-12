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

- Anonymous and free users can run the public no-AI lookup and quick-research lane without consuming model quota.
- A signed-in free user receives 5 weekly platform-API quick-analysis trials in the `ai_quick` bucket. The API trial action must be visibly separate from no-AI quick research and must disclose the remaining count before submission.
- Free users cannot use platform-key deep analysis unless the plan policy is changed.
- Pro users get higher quick/deep AI limits and may choose the platform API, a saved user-owned API key, or an approved local model. BYOK and local-model requests retain their separate abuse-control buckets.
- Exhausting the free platform-API trial must not disable anonymous/free no-AI lookup or quick research.
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
- The watchlist refresh may present a daily review summary with strongest move, weakest move, and data-quality flag count. It remains no-AI and private to the signed-in user.
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
- When the normal US/HK daily-history manager returns no rows or fails, the local service may use bounded Yahoo Chart daily history as `yahoo_chart_history`. A-share symbols must not be routed into this US/HK fallback.
- Historical AI reports must be visibly labeled as historical output and not current quote data. Refreshing current quote from a historical report must use the no-AI `snapshot?refresh=true` path and must not submit AI analysis.

## A-share History Resilience V94

- Direct local history retrieval uses a bounded `HISTORY_FETCH_TIMEOUT_SEC` budget, defaulting to 12 seconds, and exposes `history_timeout` or `history_unavailable` when no usable rows are available.
- The provider manager may bound individual provider calls within the total history budget. A slow provider must not block the next local request indefinitely.
- Pytdx public-host discovery is disabled by default when no `PYTDX_SERVERS` or `PYTDX_HOST`/`PYTDX_PORT` is configured. Explicit `PYTDX_AUTO_DISCOVERY_ENABLED=true` remains an opt-in local diagnostic mode.
- A-share history remains separate from the US/HK Yahoo history fallback. Timeout and stale states must remain visible and must not be presented as fresh data.

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

## Free Retention And API Trial V93

- The HomePage must distinguish three actions: public lookup, no-AI quick research, and API-backed AI analysis. “Quick analysis” must not silently consume an API trial.
- Async platform API analysis reserves its quota before queue admission; duplicate or failed queue submissions release the reservation by unique reference.
- Anonymous free lookup may read the public no-AI stock snapshot, daily history, and Kronos preview paths; private history reports, watchlists, account state, and AI analysis remain authenticated.
- Guests may see the API-trial offer, but clicking it only opens/focuses registration or login; it must not block or erase the current free snapshot.
- The same-symbol comparison stores only bounded quote/indicator observations in versioned browser storage. It must not store credentials, API keys, account data, full reports, or another user’s private data.
- A second query for the same market/symbol may compare price, daily move, MA20 position, signal score, freshness, volume signal, and warning count against the prior browser observation.
- The comparison must truthfully label first-observation, unchanged, and changed states and remain no-AI.
- The local daily-watchlist review, browser comparison, and Yahoo history fallback are retention aids only. They do not constitute investment advice or a production-market-data SLA.

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

## Free API Trial Result Loop V95

- A signed-in free user may use only the bounded weekly platform-API trial bucket; this flow does not create an unlimited free API lane.
- A successful asynchronous trial submission must preserve its accepted task id in the client state when the backend returns one.
- The accepted task must enter the local active-task list before SSE updates are applied, so a fast completion event cannot leave the result card stuck in a pending state.
- The HomePage must show a localized pending/processing state and bounded progress while the trial task is active.
- Completed tasks must state that history was refreshed. Failed or cancelled tasks must remain visibly failed and must not be presented as a completed report.
- No plaintext API key, token, provider secret, or task payload is written to browser storage by this result loop.
- No-AI lookup remains available while the trial task runs. Pro users may continue to select platform API, BYOK, or local model according to their separate quota buckets.
- This is a local-only retention improvement. It does not approve real payment, production API keys, hosting SLA, or investment advice.

## Free Trial Report Conversion V96

- A completed free platform-API trial should automatically open the newly created report instead of leaving the user on the no-AI snapshot.
- The client must match a report created after trial submission, for the same normalized stock symbol, and outside the pre-submit history-id baseline. An older report must not be reopened as the trial result.
- History-list refreshes may replace an in-flight lookup. The newest lookup must be allowed to match the report; a cancelled older lookup must not keep the flow locked.
- The opened report may show a localized premium-options band for the signed-in free user. It must explain the existing Platform API, user API, and local-model choices without hiding the report content.
- The premium-options action navigates to the existing account page. It must not create checkout, change plan, or imply that real payment is enabled.
- The V96 flow remains local-only, uses the existing bounded weekly trial quota, stores no credentials, and does not constitute investment advice.

## Free Retention Funnel V97

- The local retention funnel accepts only five events: `free_query_completed`, `registration_completed`, `api_trial_submitted`, `trial_report_opened`, and `premium_options_viewed`.
- Public event writes are rate-limitable and accept only a versioned browser session id plus a fixed source. Arbitrary metadata, email, stock code, report text, API keys, tokens, and payment data are rejected.
- The browser session id is hashed before persistence. The raw id must never be written to platform audit storage or returned by admin APIs.
- Duplicate event/session pairs are suppressed for the same local day so UI re-renders and repeated clicks do not inflate the ledger.
- The administrator funnel is admin-only and uses a bounded 1-90 day window. It returns aggregate unique-session counts, reached-from-start counts, drop-off counts, and conversion percentages without session or user identifiers.
- General admin audit output strips the internal retention session hash and may expose only the fixed event source.
- Frontend tracking is best-effort. Telemetry failure must never block free lookup, registration, API-trial submission, report opening, or account navigation.
- V97 remains local-only, no-AI aggregation. It is not cross-site tracking, production analytics approval, real payment, or investment advice.

## Watchlist Event Radar V99

- `GET /api/v1/platform/watchlist/radar` is authenticated and scoped to the current platform user. It must never return another user's watchlist, account data, API key, token, or raw provider error.
- The radar is no-AI by default. It does not consume platform API, BYOK, or local-model quota and does not run public search or live intelligence-feed ingestion.
- Market events are deterministic summaries of current price movement, MA20 position, volume versus MA5, and data freshness. Missing or stale data must remain visible as a data-quality event.
- A source update may be shown only when an already persisted intelligence item has a title, source, timestamp, and valid HTTP(S) URL. Placeholder quick-snapshot copy is not a news event.
- Free and paid plans use the same visible radar structure. Free processes up to 10 watchlist symbols per review; pro, premium, and enterprise process up to 50. Symbols beyond the current review limit remain stored and are not deleted.
- Suggested alerts are informational observation conditions only. V99 does not write them into the existing global alert table because that table does not yet provide platform-user ownership.
- V99 remains local-only. It does not approve production market-data licensing, real payment, production deployment, or investment advice.

## Private Watchlist Alert Loop V100

- `POST /api/v1/platform/watchlist/radar/run` is an authenticated user-owned write. It stores a bounded no-AI radar snapshot and returns only the current user's triggered alerts.
- `GET /api/v1/platform/watchlist/radar/history` and `/watchlist/alert-rules` are private to the current user. Cross-user rule deletion must return `404` and must not reveal whether another user's rule exists.
- Free users may enable up to 3 private alert rules. Pro, premium, and enterprise users may enable up to 50. Both plans keep the same visible rule, trigger, and review-history structure.
- Supported rules are `price_move`, `ma20_cross`, `volume_change`, `source_update`, and `data_quality`. Price and volume thresholds must be positive and bounded.
- MA20 crossing is stateful: the first saved run establishes a comparison baseline and cannot claim a crossing. A later run triggers only when price truly changes sides relative to MA20.
- Source-update alerts require an already persisted event with a valid HTTP(S) source URL. V100 does not enable public search or live intelligence-feed ingestion.
- Persisted radar payloads are deliberately cropped and must not contain API keys, tokens, passwords, raw provider errors, or full private reports.
- Deleting a rule hides and disables its internal row instead of hard-deleting it, so a concurrent radar run or saved review event never keeps a dangling rule reference. Re-saving the same user/symbol/type may safely re-enable that row.
- The effective rule list and execution set are capped again on every request by the current plan, so a paid-to-free downgrade cannot keep executing more than 3 rules.
- Source-update rules compare traceable URLs with the prior saved run and do not repeat the same stored source on every refresh.
- V100 local writes serialize same-user radar runs, rule saves, and rule disables inside the single local application process; multi-worker production coordination remains outside the local-only scope.
- Persisted symbol-scoped sources are checked through bounded A-share and HK code variants such as `600519.SH`, `SH600519`, `HK00700`, and `00700.HK` before the name fallback is used.
- V100 remains local-only, no-AI by default, informational analysis only, and not investment advice. It does not approve real payment, production keys, deployment, or market-data licensing.

## Free Historical Trend Research V101

- Guest and signed-in users may open the same free historical trend research panel from quick analysis without consuming AI quota.
- The panel reads the existing public daily-history endpoint and supports bounded 30, 90, 180, and 365-day ranges. Range changes must not submit AI analysis or public search.
- Visible evidence includes actual close history, MA5, MA20, volume, range return, high/low, maximum drawdown, source label, and deterministic next-check conditions.
- The panel must distinguish actual historical data from Kronos/local-rule forecast scenarios. It must not call moving-average rules a model prediction.
- Empty, incomplete, or failed public history sources degrade visibly without exposing raw provider exceptions, credentials, headers, or internal stack traces.
- When the quick snapshot already contains a bounded close-price trend, the panel renders that evidence immediately while the full selected range refreshes. A failed full-history refresh must keep the snapshot evidence visible and label it as close-only degraded data.
- Chinese and English copy must remain complete, the mobile panel must not introduce horizontal overflow, and all output remains informational analysis only, not investment advice.

## A-share Free Query Speed V102

- Free A-share quick analysis keeps the same quote, technical, announcement, fund-flow, sector, research, dragon-tiger, K-line, and risk structure. Performance work must not remove those visible lanes.
- Announcement, fund-flow, sector, research, and dragon-tiger enrichment requests are independent and run concurrently under one default 1.5-second total budget.
- A channel that exceeds the total budget degrades independently. The quote, history, technical evidence, and already completed channels must remain available without waiting for every upstream source.
- A timeout placeholder is cacheable as an explicit degraded result so an immediate repeated query does not wait on the same slow source. A later successful background completion may replace that placeholder.
- The built-in adapter reuses a process-local TTL cache across request-scoped service instances. Custom or injected adapters remain instance-local by default, preventing unrelated provider state from mixing.
- Cached timeout placeholders remain visibly degraded through diagnostics and channel status. They must never be presented as fresh source data.
- Optional peer/reference quote requests must honor the existing source-health cooldown. A cooling source returns an unavailable reference row immediately instead of adding another timeout to the main free snapshot.
- V102 does not invoke AI, public search, real payment, or production credentials. Public market data may still be delayed or incomplete, and all output remains informational analysis only, not investment advice.

## Free Daily Research Cockpit V103

- A signed-in free user can run the existing private watchlist review and receive the same daily research workflow shown to paid plans. Free and paid plans differ in capacity, data sources, refresh automation, and model depth rather than hiding the core research structure.
- Each processed symbol receives a deterministic research brief with one of three states: `strong_confirmation`, `risk_review`, or `wait_for_confirmation`.
- The brief exposes structured evidence codes, a next-watch condition, an invalidation condition, priority score, and data-confidence level. It does not generate trading instructions or claim model inference.
- Stale, unavailable, warning-bearing, or otherwise degraded data must be low-confidence and must never enter `strong_confirmation`, regardless of price move or signal score.
- The daily digest shows no more than three symbols per group and separately counts fresh, cached, stale, and unavailable data so users can distinguish research priority from source quality.
- Opening a symbol from the cockpit is a no-AI navigation action and does not consume quota. A platform API trial is charged only after the user explicitly chooses the existing real-time enhancement action on the stock page.
- The cockpit remains private to the authenticated platform user and reuses the existing V99/V100 user-isolation, current-plan limits, CSRF, rate-limit, persisted-review, and alert-rule boundaries.
- V103 is local-only and does not enable public search, real payment, production keys, deployment, or market-data licensing. All content remains informational analysis only, not investment advice.
## V104 Market Data Screening And Alert Boundary

- Public market screening is an information-and-data feature. It does not require login and defaults to deterministic `use_llm=false` execution.
- A completed no-AI screen must be labeled as AI unused, not as an LLM failure or degradation.
- Built-in strategy presentation uses neutral filter names and factual metric descriptions; it must not present entry opportunities, trading signals, target prices, or return forecasts.

- The screening page provides market information, observed metrics, source freshness, data coverage, comparison, watchlist actions, and user-defined condition alerts only.
- Anonymous users may read screening status/strategies/hotspots and run the no-AI screening task. AlphaSift install and configuration writes remain authenticated administrative actions.
- Only a platform administrator or the existing local administrator session may change the AlphaSift feature flag. Ordinary users never receive a configuration-write control.
- DSA must not present buy/sell/hold instructions, target prices, return forecasts, guaranteed outcomes, or model output as an investment recommendation.
- Alerts report observed data events against thresholds chosen by the user. They are notifications, not trading instructions.
- Free and paid users see the same information architecture. Paid capability may improve source/API availability or user-supplied API access, but must not change the information-only boundary.
- The current deterministic screening universe is A-share (`cn`). Other markets must not be claimed until their screening data contract is implemented and verified.
- Every screening surface must keep a visible reminder that the product provides information and data only and does not provide investment advice.

## V105 Fast Useful Market Screening

- Anonymous and free users use a recent full-market snapshot by default, without AI or an API key.
- A forced source refresh is explicit and slower; cache provenance, snapshot time, age, and elapsed time remain visible.
- Result cards may show price, change, PE, PB, turnover, trading value, market cap, and neutral factor labels when present.
- Sorting and secondary filtering run locally and do not consume AI or platform quota.
- The recent-snapshot fast path does not block on per-symbol network enrichment; detailed company data loads only after the user opens a symbol.
- No-AI screening does not run AlphaSift pre-rank candidate-context providers; those providers are reserved for an explicitly selected AI/deep path.
- A cache inside the selected V105 TTL is labeled as cached data, not as unavailable or a stale-source failure.
- The default TTL is market-aware: 5 minutes during the A-share session, 18 hours on weekday off-hours, and 72 hours on weekends. Forced refresh always bypasses the cache.
- Long source refreshes keep reporting bounded, elapsed-time progress below 90%; the UI must not present a fixed 75% state as completed work.
- Every V105 surface remains information-and-data only and must not produce buy/sell/hold instructions, target prices, or expected returns.

## V106 Financial Research Workflows

- Anonymous, free, and paid users may open the same four research workflows: company snapshot, operating-data review, sector overview, and public-event calendar.
- V106 reads the existing DSA no-AI stock snapshot. It does not run an external agent, public search, Claude API, or an MCP connector.
- The local `anthropics/financial-services` checkout is a read-only research-method reference. Its presence is not a market-data license, redistribution approval, or production connector approval.
- Only four explicitly allowlisted source references are recognized. Investment-banking, private-equity, wealth-management, KYC, accounting, transaction, and recommendation workflows remain disabled.
- Missing facts remain visible as `partial`; V106 must not infer or fabricate revenue, profit, sector, events, valuation, or freshness fields.
- Placeholder news, filing, profile, and data-quality lanes are context only and must not make the public-event calendar `available`; at least one non-placeholder event source is required.
- Monetary and quantity facts carry explicit currency/unit metadata, and upstream growth percentages must not be scaled a second time in the browser.
- The third-party reference is considered installed only when its Apache-2.0 license, allowlisted files, and accepted commit all match.
- Chinese and English surfaces must show source installation, Apache-2.0 attribution, connector-disabled state, external-code-not-executed state, AI usage, and the information-only boundary.
- V106 does not produce buy/sell/hold instructions, target prices, expected returns, guaranteed outcomes, or investment recommendations.

## V107 Ollama Local AI Retention

- Guest users continue to receive no-AI quote lookup and free deterministic research without login.
- Signed-in free users may use the local Ollama lane under the separate `ai_local` weekly quota. Paid plans receive a larger local quota; platform API and BYOK remain separate buckets.
- Fast local analysis and deep local analysis use separately configured models. A missing deep model must not disable an available fast lane.
- Local mode never falls back to a paid remote provider. Disabled, unreachable, missing-model, busy and timeout states degrade explicitly without consuming a failed preflight quota.
- A synchronous local request that fails after reservation but before producing a report releases its uniquely referenced `ai_local` reservation and returns a stable local-model error code.
- The public local-model status endpoint exposes readiness and model labels only. It must not expose base URLs, paths, prompts, headers, environment values or keys.
- Local-model reports provide information and data only. Before persistence, action labels are neutralized and target price, entry, stop-loss, take-profit, position sizing and action checklist fields are cleared.
- Current and legacy Ollama reports are sanitized on read without deleting or rewriting stored user data. Their cards and report summaries use an information-only label instead of buy/sell/hold labels.
- The legacy base weekly-quota view counts only platform `ai_quick` usage. `ai_local` usage is charged exclusively to the local-model bucket and must not reduce the platform API trial balance.
- V107 is local development functionality. It does not approve production deployment, real payment, market-data licensing or public model capacity.

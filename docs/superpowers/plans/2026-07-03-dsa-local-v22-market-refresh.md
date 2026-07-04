# DSA Local V22 Market Refresh

Date: 2026-07-03

Scope: local-only current-market refresh loop on top of V21 public user flow. This does not approve public launch, production deployment, real payment, production secrets, or investment advice.

## Goal

Make current quick snapshots refreshable without invoking AI:

- `GET /api/v1/stocks/{symbol}/snapshot` remains cache-first and no-AI.
- `GET /api/v1/stocks/{symbol}/snapshot?refresh=true` bypasses local snapshot cache, fetches deterministic market data, then updates cache.
- Refresh diagnostics expose `force_refresh`, requested state, quote/history cache states, freshness, fallback, and source health.
- HomePage shows a current snapshot refresh button after a quick query.
- Refreshing the snapshot must not call AI analysis and must not consume AI quota.
- External market source failures may degrade the snapshot, but must not be presented as complete fresh data.

## Verification

The V22 verifier is:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_refresh_v22.py
```

It prints `DSA_PLATFORM_LOCAL_MARKET_REFRESH_V22_OK` only when required local checks pass. The optional live 8018 refresh smoke may report degraded market-source behavior instead of pretending live data is complete.

Targeted checks:

- `tests.test_platform_local_market_refresh_v22`
- Frontend stock API and HomePage target tests
- Source-shape check for `force_refresh`, `refresh=true`, refresh diagnostics, and no-AI guardrails
- Optional live local user refresh smoke with an `e2e+` account namespace

## Boundaries

- Local-only.
- Not real payment.
- Do not commit real API Key.
- No production deployment, domain, HTTPS, WAF, or cloud resource changes.
- No deletion of reports, database rows, historical analyses, or user data.
- Not investment advice. All analysis remains informational only.

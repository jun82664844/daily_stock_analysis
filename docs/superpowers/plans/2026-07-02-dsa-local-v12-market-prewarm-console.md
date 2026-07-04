# DSA Local Market Prewarm Console V12

Date: 2026-07-02

Scope: local-only operator upgrade for the DSA platform. This stage adds an AdminPage control that prewarms the existing no-AI market cache for A-share, US, HK, and crypto smoke symbols, then refreshes the local source-health panel.

## Goals

1. Keep all work local-only. No production deployment, real payment, real API Key handoff, public launch approval, or investment-advice claim.
2. Reuse the existing `/api/v1/stocks/prewarm` endpoint and `stocksApi.prewarm()` client.
3. Add a clear AdminPage action for local cache prewarm using the default smoke symbols: `600519`, `AAPL`, `HK00700`, and `BTC-USD`.
4. Display the latest prewarm result with requested, warmed, degraded, elapsed time, symbol list, and `No AI used`.
5. Refresh `/api/v1/stocks/sources/health` after prewarm so the operator can immediately see cooldown, latency, source priority, and cache state.
6. Do not expose plaintext API keys, tokens, raw headers, local absolute paths, or raw provider exceptions in the AdminPage.

## Non-goals

- No real payment or merchant integration.
- No production DNS, HTTPS, WAF, CDN, server deployment, or production secret rotation.
- No public SearXNG enablement.
- No deletion of reports, history, user data, databases, or static build output.
- No claim that any generated analysis is investment advice.

## Implementation Plan

1. Add a failing AdminPage test for the new prewarm button and result summary.
2. Add AdminPage state for prewarm loading, error, and latest result.
3. Wire the button to `stocksApi.prewarm(DEFAULT_PREWARM_SYMBOLS)`.
4. Refresh `stocksApi.marketSourceHealth()` after successful prewarm without reloading all admin data.
5. Add V12 verifier that checks required files, gitignore visibility, frontend target tests, V11 compatibility, optional live prewarm, and the `DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK` marker.
6. Update release package verifier, review slices, release manifest, and local acceptance status.

## Verification

```powershell
cd apps\dsa-web
npm test -- --run src/pages/__tests__/AdminPage.test.tsx
npm run build
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_market_prewarm_console_v12.py
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
git diff --check
```

The V12 verifier must print `DSA_PLATFORM_LOCAL_MARKET_PREWARM_CONSOLE_V12_OK` only when required local checks pass. Optional live checks may degrade if public market sources are unavailable, but `ai_used` must remain false.

# DSA V94 A-share History Resilience

Date: 2026-07-10

Scope: local-only improvement for the public/free no-AI history lane. No production deployment, payment, real API key, or data deletion.

## Problem

The A-share history manager tried several providers sequentially and treated built-in Pytdx public hosts as available even when no server was configured. A blocked host could make a direct history request wait for every host in the list.

## Changes

- Efinance A-share history calls use the bounded `EFINANCE_HISTORY_CALL_TIMEOUT` value, defaulting to 8 seconds.
- The daily provider manager accepts an optional total `timeout_seconds` budget and bounds each provider call with a daemon worker.
- `StockService` uses `HISTORY_FETCH_TIMEOUT_SEC`, defaulting to 12 seconds, for direct history retrieval and returns an explicit degraded source when the route times out.
- Pytdx is skipped by default unless `PYTDX_SERVERS` or `PYTDX_HOST`/`PYTDX_PORT` is configured. Operators may explicitly opt into built-in host discovery with `PYTDX_AUTO_DISCOVERY_ENABLED=true`.
- Successful history responses preserve the provider source for UI diagnostics.

## Acceptance

- A slow provider cannot keep the bounded manager call open beyond its total budget.
- Unconfigured Pytdx is not entered by the web history route.
- Explicit Pytdx server configuration remains supported.
- A-share history failures remain honest degraded/empty results and do not use the US/HK Yahoo fallback.
- Existing free quick snapshots remain no-AI and continue to use their own 4-second fetch budget.

## Verification

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_history_resilience_v94 tests.test_efinance_history_timeout
```

Rollback: revert `data_provider/base.py`, `data_provider/efinance_fetcher.py`, `data_provider/pytdx_fetcher.py`, and `src/services/stock_service.py` together with the V94 regression test. Do not delete market cache, reports, database files, or user data.

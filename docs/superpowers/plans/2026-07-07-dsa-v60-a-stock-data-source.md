# DSA V60 A-Stock-Data Source Adapter

Status marker: `DSA_PLATFORM_A_STOCK_DATA_V60_OK`

## Goal

Turn the V59 local A-share enrichment POC into a configurable `a-stock-data` source adapter. The adapter can point at the locally cloned `simonlin1212/a-stock-data` skill repository, expose source diagnostics, and keep no-AI quick queries stable through cache, rate limit, and degraded fallback behavior.

## Local Install Boundary

- Stage boundary: local-only.
- External repository: `C:\Users\26879\Documents\Codex\external\a-stock-data`
- The repository is used as a local reference adapter source, not as executable trusted server code.
- `external calls disabled by default`; live source calls require explicit `A_STOCK_DATA_HTTP_ENABLED=true` or an injected `http_get` adapter.
- No real payment, no production deployment, no production secret, and no public data-source licensing approval are included in this stage.
- Do not commit real API Key.
- Output remains information analysis only; not investment advice.

## Source Controls

- `A_STOCK_DATA_SOURCE_MODE=poc|a_stock_data|off`
- `A_STOCK_DATA_CACHE_TTL_SEC=600`
- `A_STOCK_DATA_MIN_INTERVAL_SEC=1`
- `A_STOCK_DATA_SKILL_ROOT=C:\Users\26879\Documents\Codex\external\a-stock-data`
- `A_STOCK_DATA_SKILL_REVISION=<optional local revision>`

## Acceptance

- `AShareEnrichmentService(source_mode="a_stock_data")` calls `a-stock-data://announcements`, `capital_flow`, `sector`, `research`, and `dragon_tiger` channels through dependency-injected HTTP/source code only.
- Cache prevents duplicate source calls inside the TTL.
- Rate limit reuses stale cached data when available and marks the payload degraded instead of blocking the query.
- A failed channel degrades only that channel; successful channels remain visible.
- API schema exposes `source_mode`, `skill`, and `diagnostics` without exposing API keys.
- `scripts/verify_platform_a_stock_data_v60.py` prints `DSA_PLATFORM_A_STOCK_DATA_V60_OK` only when the V60 markers are present.

## Verification Commands

```powershell
C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe -m unittest tests.test_a_share_enrichment_service tests.test_platform_a_stock_data_v60
C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe scripts\verify_platform_a_stock_data_v60.py
git diff --check
```

# DSA V61 A-Stock-Data UI Source Control

Status marker: `DSA_PLATFORM_A_STOCK_DATA_UI_V61_OK`

## Goal

Expose the V60 `a-stock-data` source adapter as a local UI control so A-share users can compare local rules, the configured `a-stock-data` adapter, and an off mode without using AI or public search.

## Local Boundary

- Stage boundary: local-only.
- This does not approve production deployment, public data-source redistribution, real payment, or market-data licensing.
- Do not commit real API Key.
- Output remains information analysis only; not investment advice.

## Acceptance

- `GET /api/v1/stocks/{code}/snapshot` accepts `a_share_source_mode=poc|a_stock_data|off`.
- HomePage renders `a-share-source-control` inside the A-share enrichment card.
- The control shows cache diagnostics, local repository revision, and rate-limit counts without exposing secrets.
- Users can switch to `a-stock-data` from the page and trigger a refreshed snapshot.
- Users can run sample probes for `600519` and `000001` from the same panel.
- Frontend API maps `aShareSourceMode` to `a_share_source_mode`.
- Tests verify the endpoint parameter, API URL, and HomePage interaction.

## Verification Commands

```powershell
C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe -m unittest tests.test_basic_query_no_ai tests.test_platform_a_stock_data_ui_v61
cd apps\dsa-web
npm run test -- src/api/__tests__/stocks.test.ts src/pages/__tests__/HomePage.test.tsx
npm run build
cd ..\..
C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe scripts\verify_platform_a_stock_data_ui_v61.py
git diff --check
```

# DSA Local V24 History Center

Status: local-only functional closure. No-go for production launch.

OK marker: `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V24_OK`

## Goal

Make the local history center harder to confuse with current quotes:

- Show a dedicated History Center in the Home page sidebar.
- Filter loaded local history by market/code/report type/time/refresh status.
- Sort by generated time.
- Mark a historical report as `Current quote refreshed` only after the no-AI current quote refresh succeeds.
- Keep non-refreshed historical reports visibly marked as `Not refreshed`.

## Boundaries

- This is local-only.
- Not real payment.
- Not production deployment.
- Not investment advice.
- Do not commit real API Key.
- Do not delete history reports, databases, user data, or cached reports.
- The refresh marker is session-only and does not mutate historical report rows.
- Refreshing current quote does not rewrite old AI reports.

## Implementation Shape

- `HomePage.tsx` mounts `HistoryList` as a History Center beside the existing stock bar.
- Filters are frontend-local over the currently loaded history page.
- Market inference is based on symbol shape for A-share, US, HK, and crypto symbols.
- The refresh button still calls the no-AI current quote path and requires `snapshot?refresh=true` behavior through `stocksApi.snapshot(symbol, { refresh: true })`.
- The current quote refresh path must not call the deep AI analysis API.

## Required Local Checks

- `python -m unittest tests.test_platform_local_history_center_v24`
- `npm run test -- --run src/pages/__tests__/HomePage.test.tsx -t "filters the history center"`
- `python scripts/verify_platform_local_history_center_v24.py`

The verifier checks source shape, documentation safety copy, gitignore visibility, and the focused frontend behavior.

# DSA Local V25 History Center Persistence

Status: local-only functional closure. No-go for production launch.

OK marker: `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V25_OK`

## Goal

Upgrade the local History Center from frontend-only loaded-page filtering to backend filtering, stable pagination, and a persistent refresh marker:

- Backend filtering for market/code/report type/time/refresh state.
- Stable newest/oldest sorting with pagination.
- Persistent refresh marker for no-AI current quote refreshes.
- User-scoped marker access so one platform user cannot mark or view another user's history marker.
- Frontend filter controls call the backend instead of filtering a partial loaded page.
- Refreshed badges survive reload through the marker returned by the history API.

## Boundaries

- This is local-only.
- Not real payment.
- Not production deployment.
- Not investment advice.
- Do not commit real API Key.
- Do not delete history reports, databases, user data, or cached reports.
- The persistent refresh marker is stored in a side table and does not rewrite old AI reports.
- Refreshing current quote uses the no-AI quick snapshot path and does not run deep AI analysis.

## Implementation Shape

- `AnalysisHistoryRefreshMarker` stores one low-risk no-AI marker per history record and platform user.
- `/api/v1/history` accepts `market`, `refresh_status`, and `sort` query params and includes `current_quote_refreshed` metadata in list items.
- `/api/v1/history/{record_id}/refresh-marker` writes marker metadata only after a no-AI current quote refresh succeeds; requests with `ai_used=true` are rejected.
- `historyApi.getList` sends backend filter params and `historyApi.markCurrentQuoteRefreshed` writes the marker.
- `stockPoolStore` owns `historyFilters` so refresh and load-more stay aligned with the current History Center view.
- `HomePage` maps UI filters into backend parameters and calls marker persistence after `stocksApi.snapshot(symbol, { refresh: true })` succeeds.

## Required Local Checks

- `python -m unittest tests.test_platform_local_history_center_v25`
- `npm run test -- HomePage.test.tsx`
- `python scripts/verify_platform_local_history_center_v25.py`

The verifier checks backend/frontend source shape, local-only documentation boundaries, gitignore visibility, and focused backend/frontend tests.

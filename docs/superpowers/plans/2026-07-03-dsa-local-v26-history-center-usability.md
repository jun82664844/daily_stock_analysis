# DSA Local V26 History Center Usability

Status: local-only functional closure. No-go for production launch.

OK marker: `DSA_PLATFORM_LOCAL_HISTORY_CENTER_V26_OK`

## Goal

Make the local History Center more usable for repeated user sessions without changing old report content:

- Persist History Center filter controls in browser `localStorage`.
- Restore saved market/code/report type/time/refresh/sort filters after page reload.
- Apply restored filters back through the backend-filtered history API.
- Show backend total count in the History Center header instead of only the currently loaded page count.
- Keep filter storage safe with validated enum values and bounded code text.

## Boundaries

- This is local-only.
- Not real payment.
- Not production deployment.
- Not investment advice.
- Do not commit real API Key.
- Do not delete history reports, databases, user data, cached reports, or generated static output.
- This does not rewrite old AI reports and does not change persisted analysis text.
- Restored filters only affect the local UI request parameters; they do not create a new AI path.

## Implementation Shape

- `HomePage` reads `dsa-history-center-filters-v1` from `localStorage`, validates saved values, and restores the History Center controls.
- `HomePage` persists filter changes and reset state back to `localStorage`.
- `stockPoolStore` stores `historyTotal` from `historyApi.getList` responses so pagination and header display use backend totals.
- `useHomeDashboardState` exposes `historyTotal` to the page layer.
- `HistoryList` accepts `totalCount` and renders `history-total-count` for the history center.
- The focused frontend test covers restored filters, backend filter params, and backend total display.

## Required Local Checks

- `python -m unittest tests.test_platform_local_history_center_v26`
- `npm run test -- HomePage.test.tsx -t "restores history center filters"`
- `python scripts/verify_platform_local_history_center_v26.py`

The verifier checks source shape, local-only documentation boundaries, gitignore visibility, and focused backend/frontend proof. It does not connect real payment, real API keys, or production services.

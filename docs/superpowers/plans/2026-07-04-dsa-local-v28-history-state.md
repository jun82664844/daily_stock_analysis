# DSA Local V28 History State

Date: 2026-07-04

Marker: `DSA_PLATFORM_LOCAL_HISTORY_STATE_V28_OK`

Scope: local-only history report management. This is not public launch approval.

## Outcome

- Add owner-scoped local history state for favorite, important, archived, read, and note.
- Store state in the side table `analysis_history_user_states` instead of rewriting old AI reports.
- Add no-AI APIs for single-record state updates and batch archive/unarchive.
- Extend History Center filtering with local state filters.
- Add History Center batch archive/restore and detail-panel favorite/important/read/archive/note controls.

## Safety Boundaries

- Local-only.
- Not real payment.
- Do not commit real API Key.
- Do not delete history reports, databases, user data, cached reports, or static build output.
- State updates are no-AI operations and return `ai_used=false`.
- Ordinary users can only update owner-scoped records.
- Existing report content remains historical and is not rewritten into current market data.
- All analysis content remains informational only and is not investment advice.

## Verification

- Backend unit: `python -m unittest tests.test_platform_local_history_state_v28`
- Frontend focused test: `npm run test -- HomePage.test.tsx -t "manages local history state"`
- Verifier: `scripts\verify_platform_local_history_state_v28.py`
- Expected verifier marker: `DSA_PLATFORM_LOCAL_HISTORY_STATE_V28_OK`

## Not In Scope

- Public deployment, production domain, HTTPS/WAF, production database migration, production secrets, real API keys, real payment, refunds, invoices, legal copy finalization, and commercial pricing.

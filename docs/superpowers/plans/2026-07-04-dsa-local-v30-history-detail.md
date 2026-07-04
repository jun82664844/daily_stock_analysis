# DSA Local V30 History Detail Tools

Date: 2026-07-04

Marker: `DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK`

Scope: local-only historical report detail usability. This is not public launch approval.

## Outcome

- Add no-AI report detail search across visible historical report summary, strategy, news, board, sector, and diagnostic text.
- Add previous/next search navigation and a visible match counter inside the selected historical report detail view.
- Add section jumps for Summary, Strategy, News, Diagnostics, and Details through stable report section anchors.
- Add a same-stock timeline inside the selected report detail view so users can move between older reports for the same stock.
- Reuse the existing owner-scoped history list and selected history detail APIs. Do not add a new timeline endpoint for this local-only detail tool.

## Safety Boundaries

- Local-only.
- Not real payment.
- Do not commit real API Key.
- Do not delete history reports, databases, user data, cached reports, or static build output.
- Report detail search, section jumps, and same-stock timeline navigation are no-AI operations and must not consume AI quota.
- Same-stock timeline data must come from owner-scoped history records already returned by the existing history list path.
- Existing historical report content remains historical and is not rewritten into current market data.
- All analysis content remains informational only and is not investment advice.

## Verification

- Verifier unit: `python -m unittest tests.test_platform_local_history_detail_v30`
- Frontend focused test: `npm run test -- HomePage.test.tsx -t "adds no-AI report detail"`
- Verifier: `scripts\verify_platform_local_history_detail_v30.py`
- Expected verifier marker: `DSA_PLATFORM_LOCAL_HISTORY_DETAIL_V30_OK`

## Not In Scope

- Public deployment, production domain, HTTPS/WAF, production database migration, production secrets, real API keys, real payment, refunds, invoices, legal copy finalization, and commercial pricing.

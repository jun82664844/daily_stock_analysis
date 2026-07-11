# DSA V105 Fast Useful Market Screening

## Outcome

Make the free, no-AI market screening page fast enough for repeat use and rich enough to support factual comparison without presenting investment advice.

## Product boundary

- Information and observed market data only.
- No buy/sell/hold wording, target prices, expected returns, or trading instructions.
- Anonymous users can run the default cached-data screen without an API key.
- A manual source refresh remains available and is explicitly labeled as slower.

## Delivery scope

1. Prefer a recent full-market snapshot for repeat screens.
2. Use a short cache window during A-share trading hours and a longer window outside trading hours.
3. Allow a caller to force a live-source refresh.
4. Return cache provenance, snapshot timestamp, age, and elapsed time.
5. Surface price, change, PE, PB, turnover, amount, and market-cap metrics when present.
6. Localize internal factor names in Chinese and English.
7. Add client-side sorting and secondary filters without another network request.
8. Keep source freshness and the information-only reminder visible.

## Acceptance

- Backend cache and metric contract tests pass.
- Frontend model/page tests cover sorting, filtering, cache labels, and both languages.
- Cached repeat screening completes materially faster than forced source refresh.
- Browser acceptance covers anonymous screening and visible data provenance.
- Release-package verifier covers all changed files.
- Git is committed and clean; no push.

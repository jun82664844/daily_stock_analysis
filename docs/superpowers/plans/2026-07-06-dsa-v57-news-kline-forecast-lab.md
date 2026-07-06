# DSA V57 Local News And K-Line Forecast Lab

## Goal

Make the free local stock query feel useful enough for ordinary users to keep exploring:

- Add a no-AI information center that shows news, announcements, financial, sector, and data-quality lanes.
- Add a K-line forecast lab preview that is Kronos-ready but does not run Kronos, AI, public search, or paid API in this phase.
- Add a premium feature ladder so users can see what deeper paid analysis would unlock later.

## Boundaries

- Local-only.
- No real payment.
- No production deployment, domain, HTTPS, WAF, or cloud secret work.
- Do not commit real API Key.
- Do not delete history reports, database files, or user data.
- No AI calls in the free quick snapshot.
- No public search in the free quick snapshot.
- Forecast lab output is experimental information analysis only; not investment advice.

## Implementation Checklist

- [ ] Backend schema supports `news_center` and `kline_forecast` under `intelligence`.
- [ ] `BasicQueryService` generates deterministic no-AI news center content from route, quote, profile, indicators, and warnings.
- [ ] `BasicQueryService` generates deterministic Kronos-ready K-line forecast preview from current price, MA levels, trend, and volume-price signals.
- [ ] Frontend API types map `news_center` and `kline_forecast` into camelCase.
- [ ] `HomePage` renders the news center, K-line forecast lab, and premium feature ladder after a free query.
- [ ] V57 verifier checks static markers, no-AI boundaries, docs, and optional live 8018 payload.
- [ ] Release candidate package verifier covers the new V57 files.

## Acceptance Marker

`DSA_PLATFORM_LOCAL_NEWS_KLINE_V57_OK`

## Verification Commands

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_basic_query_no_ai tests.test_platform_local_news_kline_v57 tests.test_platform_release_candidate_package
Set-Location apps\dsa-web; npm run test -- src/api/__tests__/stocks.test.ts src/pages/__tests__/HomePage.test.tsx; npm run build
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_news_kline_v57.py --live-url http://127.0.0.1:8018
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_release_candidate_package.py
git diff --check
git status --short --branch --untracked-files=all
```

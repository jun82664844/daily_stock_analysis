# DSA Local V18 Watchlist Board Implementation Plan

Scope: local functional upgrade only.

**Goal:** Upgrade the platform-user private watchlist from a symbol strip into a no-AI multi-market board. A signed-in local platform user can refresh the watchlist, compare A-share, US, HK, and crypto quick snapshot rows, see degraded data warnings, and click a row to run the existing quick query path.

**Architecture:** V18 reuses the V17 `/api/v1/platform/watchlist/refresh` payload and the existing `BasicQueryService` quick snapshot route. The board is a frontend experience layer over refreshed rows; it does not create a new AI path, does not consume AI quota, and does not change the global `STOCK_LIST` watchlist.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, React/Vite, Vitest, Python verifier scripts.

## Tasks

- [x] Add a HomePage watchlist board rendered from refreshed watchlist rows.
- [x] Show stock code, name, market, price, change percent, freshness, route lane, no-AI status, degradation status, and warning codes.
- [x] Let each board row trigger the existing no-AI quick snapshot query for that symbol.
- [x] Add a focused V18 HomePage test that first failed because the board did not exist, then passed after implementation.
- [x] Add `tests/test_platform_local_watchlist_board_v18.py` for the V18 verifier contract.
- [x] Add `scripts/verify_platform_local_watchlist_board_v18.py`; passing output is `DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK`.
- [x] Register the V18 verifier in `.gitignore` and the release-candidate package verifier.

## Acceptance

Run:

```powershell
cd apps\dsa-web
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "watchlist board"
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_watchlist_board_v18
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_watchlist_board_v18.py
```

Expected: V18 verifier prints `DSA_PLATFORM_LOCAL_WATCHLIST_BOARD_V18_OK`.

## Boundaries

- No real payment.
- No production deployment, domain, HTTPS, WAF, CDN, cloud migration, or legal/commercial launch decision.
- No real API Key in tests, docs, verifier output, or logs.
- No deletion of reports, databases, users, API keys, billing rows, cache files, or `static/` build outputs.
- No `git add`, `git commit`, or `git push`.
- Watchlist refresh and board row quick query stay no-AI and must not consume AI quota.
- Historical reports remain separate from current quick snapshots.
- Analysis remains informational only and is not investment advice.

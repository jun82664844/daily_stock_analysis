# DSA Local V17 User Watchlist Implementation Plan

Scope: local functional upgrade only.

**Goal:** Add a private platform-user watchlist loop for local multi-user mode, with no-AI multi-market refresh across A-share, US, HK, and crypto symbols.

**Architecture:** V17 keeps the existing global `STOCK_LIST` watchlist untouched and adds a separate platform-user watchlist under `/api/v1/platform/watchlist`. Each platform user sees only their own symbols. Refresh uses the existing `BasicQueryService` quick snapshot path and must return `ai_used=false`.

**Tech Stack:** FastAPI, SQLAlchemy/SQLite, React/Vite, Vitest, Python verifier scripts.

## Tasks

- [x] Add a platform-user watchlist table scoped by `user_id` and normalized `stock_code`.
- [x] Add `PlatformWatchlistService` for list/add/remove/refresh.
- [x] Add platform endpoints:
  - `GET /api/v1/platform/watchlist`
  - `POST /api/v1/platform/watchlist`
  - `DELETE /api/v1/platform/watchlist/{stock_code}`
  - `POST /api/v1/platform/watchlist/refresh`
- [x] Add HomePage platform watchlist panel with current list, add-current action, and no-AI refresh summary.
- [x] Add V17 backend and frontend tests.
- [x] Add `scripts/verify_platform_local_watchlist_v17.py`; passing output is `DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK`.

## Acceptance

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_watchlist_v17 tests.test_platform_local_watchlist_v17_verifier
cd apps\dsa-web
npm test -- --run src/api/__tests__/platform.test.ts
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "ordinary-user account guardrails"
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_watchlist_v17.py
```

Expected: V17 verifier prints `DSA_PLATFORM_LOCAL_WATCHLIST_V17_OK`.

## Boundaries

- No real payment.
- No production deployment, domain, HTTPS, WAF, CDN, cloud migration, or legal/commercial launch decision.
- No real API Key in tests, docs, verifier output, or logs.
- No deletion of reports, databases, users, API keys, billing rows, cache files, or `static/` build outputs.
- No `git add`, `git commit`, or `git push`.
- Refresh stays no-AI and must not consume AI quota.
- Analysis remains informational only and is not investment advice.

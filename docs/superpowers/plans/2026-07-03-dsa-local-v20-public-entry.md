# DSA Local V20 Public Entry Gate

Date: 2026-07-03
Scope: local-only functional upgrade, not public launch approval.

## Goal

Keep the ordinary platform-user entry reachable at `http://127.0.0.1:8018/` while preserving administrator-only protection for operator pages.

## Background

During the local browser walk-through, the live root page rendered the admin login screen because the frontend App route guard redirected every route to `/login` when admin auth was enabled and no admin cookie was present. That blocked ordinary users from reaching the platform login/register/query UI.

## Product Boundary

- `/`, `/portfolio`, `/chat`, `/account`, and `/usage` are ordinary platform-user routes and must not require an admin session.
- `/admin` and `/settings` remain admin-only routes and continue to redirect to the admin login page when no admin session is present.
- Backend admin APIs remain protected by server-side auth; this change only fixes the public frontend entry boundary.
- Platform user login, quota, BYOK, watchlist, history, and no-AI quick query flows remain local V1 functionality.

## Files

- `apps/dsa-web/src/App.tsx`
- `apps/dsa-web/src/App.test.tsx`
- `apps/dsa-web/src/api/index.ts`
- `apps/dsa-web/src/api/__tests__/index.test.ts`
- `apps/dsa-web/src/components/layout/SidebarNav.tsx`
- `apps/dsa-web/src/components/layout/__tests__/SidebarNav.test.tsx`
- `apps/dsa-web/src/stores/stockPoolStore.ts`
- `apps/dsa-web/src/stores/__tests__/stockPoolStore.test.ts`
- `scripts/verify_platform_local_public_entry_v20.py`
- `tests/test_platform_local_public_entry_v20.py`
- `docs/superpowers/plans/2026-07-03-dsa-local-v20-public-entry.md`

## Verification

```powershell
cd C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\daily_stock_analysis_audit
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_public_entry_v20
cd apps\dsa-web
npm test -- --run src/App.test.tsx
npm test -- --run src/api/__tests__/index.test.ts
npm test -- --run src/components/layout/__tests__/SidebarNav.test.tsx
npm test -- --run src/stores/__tests__/stockPoolStore.test.ts -t "unauthenticated"
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_public_entry_v20.py
```

The verifier prints `DSA_PLATFORM_LOCAL_PUBLIC_ENTRY_V20_OK` only when the V20 route boundary, V19 compatibility, verifier tests, App route guard tests, frontend API 401 redirect guard tests, public navigation guard tests, and public-history 401 empty-state tests pass.

## Non-Goals

- No real payment.
- No production deployment.
- No real domain, HTTPS, WAF, or CDN work.
- No public SearXNG enablement.
- No real API key exposure.
- No investment advice.

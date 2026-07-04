# DSA Local V21 Public User Flow

Date: 2026-07-03

Scope: local-only ordinary-user real-use closure on top of V20 public entry. This does not approve public launch, production deployment, real payment, production secrets, or investment advice.

## Goal

Make the local 8018 public entry usable as an ordinary platform user flow:

- Public root entry must render without requiring an admin cookie.
- Ordinary users can register/login locally without exposing generated passwords in verifier output.
- Account summary must return the current user, quota, quota buckets, and masked API key state only.
- Quick snapshots for `600519`, `AAPL`, `HK00700`, and `BTC-USD` must stay no-AI and route to their market lanes.
- Private watchlist add/list/refresh must stay scoped to the platform user and must not consume AI quota.
- Ordinary users must receive 403 for admin APIs and should not see admin navigation.

## Verification

The V21 verifier is:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_public_user_flow_v21.py
```

It prints `DSA_PLATFORM_LOCAL_PUBLIC_USER_FLOW_V21_OK` only when required local checks pass. The optional live 8018 smoke may report degraded market-source behavior, route failures, or stale data instead of pretending the flow succeeded.

Targeted checks:

- `tests.test_platform_local_public_user_flow_v21`
- Frontend App, HomePage, AccountPage, and SidebarNav target tests
- V20 public-entry compatibility gate
- Optional live local user smoke with an `e2e+` account namespace

## Boundaries

- No real payment.
- No production API keys.
- No public deployment, domain, HTTPS, WAF, or cloud resource changes.
- No deletion of reports, database rows, historical analyses, or user data.
- No investment advice. All analysis remains informational only.

# DSA Local V1 Operability Verification

Date: 2026-07-01

Purpose: provide one repeatable local gate before wider trial use. The verifier does not expose API keys and does not change historical reports or user data.

## Dry Run

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py --dry-run --json
```

## Default Gate

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py
```

Default checks cover:

- no-AI basic stock query behavior
- feature-specific AI quota buckets, including pro-tier, BYOK, and local-model accounting
- user-owned API key product mode with encrypted storage and no plaintext response
- local model capacity gate
- platform security boundaries, admin/platform CSRF, and audit redaction
- platform history report owner isolation
- local V1 billing boundary
- admin backend endpoints for users, usage, audit logs, and plan changes
- admin frontend page, route, navigation, empty/failure states, and audit metadata redaction
- frontend production build
- running WebUI health and admin page shell

## Optional Live Market Provider Smoke

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py --include-optional --only live_basic_snapshot
```

This optional check calls `/api/v1/stocks/AAPL/snapshot`. It is useful for real provider smoke testing, but it can be slower or flaky when public market data providers are unavailable.

When platform user auth is enabled, provide a smoke-test user through environment variables before running the optional check:

```powershell
$env:DSA_OPERABILITY_PLATFORM_EMAIL="smoke@example.com"
$env:DSA_OPERABILITY_PLATFORM_PASSWORD="<local smoke user password>"
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py --include-optional --only live_basic_snapshot
```

The verifier only sends these credentials to the local `/api/v1/platform/login` endpoint and does not print the password. If credentials are missing and the running service requires login, the optional check is reported as `skipped` instead of failing the default gate.

For local-only convenience, the optional check can create a disposable platform smoke user explicitly:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_local_v1_operability.py --include-optional --only live_basic_snapshot --auto-smoke-user
```

This mode is opt-in and local-only. It registers an `e2e+local-smoke-...@example.com` user through the running local `/api/v1/platform/register` endpoint, uses the returned cookie for the snapshot request, and does not print the generated password. It does not delete data. Inspect the namespace with the existing dry-run cleanup helper before any manual cleanup decision:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\cleanup_platform_e2e_data.py --email-prefix e2e+ --json
```

## Interpretation

- `passed`: the check has fresh evidence.
- `planned`: dry-run only; nothing was executed.
- `skipped`: optional check could not run safely without extra local input, such as smoke-test login credentials.

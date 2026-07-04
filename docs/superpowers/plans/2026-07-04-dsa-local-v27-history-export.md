# DSA Local V27 History Export

Date: 2026-07-04

OK marker: `DSA_PLATFORM_LOCAL_HISTORY_EXPORT_V27_OK`

## Scope

Add a local-only History Center export path so selected history reports can be downloaded as Markdown or JSON bundles.

This is a local usability and data-safety gate only. It is No-go for public launch, not real payment, not production deployment, and not investment advice.

## Completed Design

- Backend adds `POST /api/v1/history/export`.
- Request body accepts `record_ids` and `format` (`markdown` or `json`).
- Record IDs are de-duplicated and capped at 50 per export.
- Ordinary platform users can export only their own history records.
- Admin/global local context keeps the existing global history behavior.
- Export uses persisted local history only. AI used: false.
- Existing Markdown generation is reused when available.
- Older or incomplete records fall back to a local summary Markdown body instead of calling AI.
- Export content is redacted for secret-like strings before response.
- JSON export includes safe metadata and summary fields only; it does not dump raw_result or API keys.

## Frontend

- `historyApi.exportReports()` calls `/api/v1/history/export`.
- History Center selection is enabled.
- The selected history export button downloads a local Markdown bundle with browser `Blob`.
- Export status is shown inline.
- Quick/no-AI, deep AI, BYOK, local model, and billing quota buckets are not changed by this gate.

## Safety Boundaries

- Do not delete history reports.
- Do not rewrite old AI report rows.
- Do not commit real API Key.
- Do not expose API keys, bearer tokens, passwords, or secret-like `sk-...` strings in export content.
- Do not connect real payment.
- Do not enable production deployment, domain, HTTPS/WAF, email/SMS, or legal launch workflow.
- All output remains informational analysis only and is not investment advice.

## Verification

Run:

```powershell
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_export_v27 -v
cd apps\dsa-web
npm run test -- HomePage.test.tsx -t "exports selected history reports"
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_export_v27.py
```

Completion requires the OK marker, passing backend/frontend focused tests, no unclassified dirty files, no secret exposure, no AI use for export, and no launch claims.

# DSA Local V23 History Snapshot Boundary

Date: 2026-07-03

Scope: local-only usability and correctness gate for separating historical AI reports from the current no-AI market snapshot. This is not public launch approval, not real payment, not production secret handling, and not investment advice. Do not commit real API Key.

## Goal

Historical reports must be visibly labeled as historical AI output and not current quote data. Users can refresh the current quote from a historical report, but that action must use the existing no-AI `snapshot?refresh=true` path instead of submitting an AI analysis.

## Implemented Boundary

- HomePage shows a visible `Historical AI report · not current quote` boundary when a historical stock report is selected.
- The historical report boundary explains that historical AI reports do not auto-refresh market prices.
- The boundary includes a current-quote refresh action for stock reports.
- The refresh action calls the current snapshot path with force refresh: `snapshot?refresh=true`.
- The refresh action does not call `analysisApi.analyzeAsync` and must not consume AI quota.
- The current snapshot branch preempts the historical report branch after refresh, so the user sees current quote diagnostics rather than stale report content.

## Verification

Primary marker:

```text
DSA_PLATFORM_LOCAL_HISTORY_SNAPSHOT_BOUNDARY_V23_OK
```

Recommended local checks:

```powershell
cd apps\dsa-web
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "marks historical reports"
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_history_snapshot_boundary_v23
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_history_snapshot_boundary_v23.py
```

## Safety

- This remains local-only.
- This is not real payment.
- This does not enable production deployment, domain, HTTPS, WAF, public SearXNG, or real merchant flows.
- Do not commit real API Key.
- All report and snapshot content remains informational only and is not investment advice.

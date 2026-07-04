# DSA Local V19 Query Workspace Implementation Plan

Scope: local functional upgrade only.

**Goal:** Make the ordinary-user query page easier to operate by separating the visible state of current quick snapshots, private watchlist, historical reports, and AI analysis controls.

**Architecture:** V19 is a frontend clarity layer inside HomePage. It reads existing local state from the quick snapshot, platform watchlist, history list, API key mode, and BYOK status. It does not add a new backend route, does not trigger AI, and does not change quota accounting.

**Tech Stack:** React/Vite, Vitest, Python verifier scripts.

## Tasks

- [x] Add a query workspace status band inside the current quick snapshot panel.
- [x] Show `Current Snapshot` with no-AI state and market lane.
- [x] Show `Watchlist` with private symbol count.
- [x] Show `History Reports` with report count and separation status.
- [x] Show `AI Analysis` with selected platform/BYOK/local mode and BYOK readiness.
- [x] Add a V19 HomePage target assertion to the ordinary-user no-AI query test.
- [x] Add `tests/test_platform_local_query_workspace_v19.py`.
- [x] Add `scripts/verify_platform_local_query_workspace_v19.py`; passing output is `DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK`.
- [x] Register the V19 verifier in `.gitignore` and the release-candidate package verifier.

## Acceptance

Run:

```powershell
cd apps\dsa-web
npm test -- --run src/pages/__tests__/HomePage.test.tsx -t "ordinary-user account guardrails"
cd ..\..
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" -m unittest tests.test_platform_local_query_workspace_v19
& "C:\Users\26879\Documents\Codex\2026-06-05\https-x-com-wy-mask-status\work\dsa-venv\Scripts\python.exe" scripts\verify_platform_local_query_workspace_v19.py
```

Expected: V19 verifier prints `DSA_PLATFORM_LOCAL_QUERY_WORKSPACE_V19_OK`.

## Boundaries

- No real payment.
- No production deployment, domain, HTTPS, WAF, CDN, cloud migration, or legal/commercial launch decision.
- No real API Key in tests, docs, verifier output, or logs.
- No deletion of reports, databases, users, API keys, billing rows, cache files, or `static/` build outputs.
- No `git add`, `git commit`, or `git push`.
- Current quick snapshots stay no-AI and must not consume AI quota.
- AI analysis remains a separate explicit action.
- Historical reports remain separate from current quick snapshots.
- Analysis remains informational only and is not investment advice.

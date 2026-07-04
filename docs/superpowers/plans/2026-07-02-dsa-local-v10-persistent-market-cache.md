# DSA Local V10 Persistent Market Cache Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a local persistent market-data cache so quick/no-AI A-share, HK, US, and crypto queries can reuse recent quote/history data after WebUI restart or source cooldown.

**Architecture:** Keep the existing quick-query route, timeout, source-health, and prewarm flow intact. Add a small JSON-backed cache implementation behind the existing `MarketDataCache` interface, then make `BasicQueryService` use it by default unless explicitly overridden in tests.

**Tech Stack:** Python standard library JSON/pathlib/threading, FastAPI schemas already present, React/Vite diagnostics already present, unittest, Vitest, existing verifier scripts.

---

## Scope

No-go: no public deployment, no real payment, no production API keys, no production secret handling, and no investment advice. Do not commit real API Key. Do not delete reports, SQLite databases, user data, or generated static build output.

V10 does not replace the data-provider framework. It adds a safer local fallback layer around the existing quick/no-AI query path.

## Files

- Create: `src/services/persistent_market_data_cache.py`
- Create: `tests/test_platform_local_persistent_market_cache_v10.py`
- Create: `scripts/verify_platform_local_persistent_market_cache_v10.py`
- Modify: `src/services/market_data_cache.py`
- Modify: `src/services/basic_query_service.py`
- Modify: `api/v1/schemas/basic_query.py`
- Modify: `apps/dsa-web/src/api/stocks.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`
- Modify: `apps/dsa-web/src/api/__tests__/stocks.test.ts`
- Modify: `.gitignore`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

## Tasks

### Task 1: RED tests

- [ ] Write `tests/test_platform_local_persistent_market_cache_v10.py`.
- [ ] Prove a disk-backed cache can persist a quote/history item across cache instances.
- [ ] Prove `BasicQueryService` uses persisted stale data when the source enters `cooling_down`, without making another live source call and with `ai_used=false`.
- [ ] Prove diagnostics include `persistent_cache` state and `disk_cache` fallback.
- [ ] Prove the V10 verifier file and marker exist.
- [ ] Run the new test and verify it fails because V10 implementation does not exist yet.

### Task 2: Persistent cache implementation

- [ ] Add `PersistentMarketDataCache`, backed by a local JSON file under `local/market_data_cache.json` by default.
- [ ] Keep max-entry and file-size behavior bounded.
- [ ] Store only market payloads, source, created time, and ttl. Do not store headers, tokens, cookies, API keys, URLs with secrets, or user identifiers.
- [ ] Extend cache hit diagnostics with `origin` so callers can distinguish memory and disk hits.

### Task 3: Query service integration

- [ ] Make the default quick-query cache persistent unless tests inject a cache.
- [ ] When live source is `cooling_down`, allow disk/stale cache hits to satisfy quote/history first.
- [ ] Preserve existing V8/V9 diagnostics: `timeouts`, sanitized `errors`, `fallback`, `source_health`, route lane, and `ai_used=false`.
- [ ] Add `persistent_cache` diagnostics with cache mode and storage path redacted to a local marker instead of an absolute path.

### Task 4: Frontend diagnostics

- [ ] Extend `BasicStockSnapshot.diagnostics` with `persistentCache`.
- [ ] Show a compact cache mode chip in HomePage.
- [ ] Keep text short and avoid raw paths or secret values.
- [ ] Update existing HomePage/stocks API tests.

### Task 5: V10 verifier and release package

- [ ] Add `scripts/verify_platform_local_persistent_market_cache_v10.py`, marker `DSA_PLATFORM_LOCAL_PERSISTENT_MARKET_CACHE_V10_OK`.
- [ ] Verify required files, `.gitignore` visibility, V10 unittest, V9 compatibility, optional live prewarm/snapshot diagnostics.
- [ ] Update release-candidate package verifier/test/docs to cover the new dirty files and marker.

### Task 6: Verification

- [ ] Run V10 unittest.
- [ ] Run V4-V10 backend quick-query regression group.
- [ ] Run frontend target Vitest group and `npm run build`.
- [ ] Run `npm run test:smoke`.
- [ ] Restart 8018 if needed and run V10 live verifier.
- [ ] Run V1/V2/V4-V10 verifiers as needed.
- [ ] Run `scripts/verify_platform_release_candidate_package.py`.
- [ ] Run `git diff --check` and final dirty inventory.

# DSA V102 A-share Free Query Speed Implementation Plan

> **For agentic workers:** Use `executing-plans` or an available multi-agent workflow to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Keep the free A-share research page useful while bounding the five-channel enrichment cost and making repeated local queries materially faster.

**Architecture:** Retain the existing no-AI snapshot contract and A-share enrichment payload. Fetch independent announcement, fund-flow, sector, research, and dragon-tiger channels concurrently under one total budget, and reuse only default-adapter payload caches across request-scoped service instances. Slow or failed channels degrade independently and never block quote/history output.

**Tech Stack:** Python 3, `concurrent.futures`, FastAPI, unittest, existing DSA verifier stack, React/Vitest browser acceptance.

---

### Task 1: Lock the performance contract with failing tests

**Files:**
- Modify: `tests/test_a_share_enrichment_service.py`

- [ ] Add a test where five channel calls each sleep briefly and assert total elapsed time proves concurrent execution.
- [ ] Add a test where a channel ignores its per-call timeout and assert the overall enrichment budget returns a degraded payload without waiting for the slow call.
- [ ] Add a test where two default-adapter service instances query the same symbol and assert the second instance reuses five cached channel payloads.
- [ ] Run `python -m unittest tests.test_a_share_enrichment_service -v` and confirm the new tests fail for the missing behavior.

### Task 2: Implement bounded concurrent enrichment

**Files:**
- Modify: `src/services/a_share_enrichment_service.py`

- [ ] Add a bounded module executor and configurable `A_STOCK_DATA_TOTAL_TIMEOUT_SEC` budget.
- [ ] Isolate per-channel diagnostics so worker completion cannot mutate a response after the budget has expired.
- [ ] Merge completed channel results in the stable `CHANNELS` order and mark budget-expired channels explicitly.
- [ ] Protect cache and request-throttle state with a lock while leaving network I/O outside the critical section.
- [ ] Re-run the focused tests and confirm concurrent, timeout, partial-degradation, and existing payload behavior pass.

### Task 3: Reuse safe cache state across API requests

**Files:**
- Modify: `src/services/a_share_enrichment_service.py`
- Modify: `src/services/basic_query_service.py`
- Modify: `tests/test_a_share_enrichment_service.py`
- Modify: `tests/test_platform_market_data_freshness_v92.py`

- [ ] Use a process-local shared cache only for the built-in default adapter; injected test/custom adapters remain instance-local unless explicitly opted in.
- [ ] Include source mode in shared cache keys so `poc`, `a_stock_data`, and disabled modes never contaminate one another.
- [ ] Keep the existing TTL, stale-rate-limit, no-AI, and no-public-search boundaries unchanged.
- [ ] Skip optional peer/reference quote calls while their source is already cooling down; keep the visible reference row as unavailable.
- [ ] Confirm a second request returns cache hits and performs no duplicate upstream calls.

### Task 4: Add V102 verification and operator evidence

**Files:**
- Create: `scripts/verify_platform_a_share_free_query_speed_v102.py`
- Create: `tests/test_platform_a_share_free_query_speed_v102_verifier.py`
- Modify: `.gitignore`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`
- Modify: `docs/CHANGELOG.md`

- [ ] Make the verifier run the focused service tests and a deterministic performance probe.
- [ ] Emit `DSA_PLATFORM_A_SHARE_FREE_QUERY_SPEED_V102_OK` only when all gates pass.
- [ ] Document that free mode keeps all five visible channels while upstream failures remain explicit degradation, not fabricated freshness.
- [ ] Add the verifier to release-package visibility and dirty-file classification.

### Task 5: Full and live acceptance

**Files:**
- Verify only; do not delete user data or reports.

- [ ] Run focused backend tests, V102 verifier, V101 verifier, local V1 operability, release-candidate verifier, frontend tests/lint/build, and whitespace/secret checks.
- [ ] Restart the local 8018 service only after confirming the listener belongs to this DSA checkout.
- [ ] Browser-query `600519` in free quick mode twice; record first and repeat elapsed time, cache diagnostics, visible degradation, quota preservation, and console errors.
- [ ] Explicitly stage only V102 files, create one local commit, do not push, and confirm `git status -sb --untracked-files=all` is clean.

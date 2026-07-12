# DSA V107 Ollama Local Retention Implementation Plan

> **For agentic workers:** Execute each task with test-first development and preserve the current V106 dirty tree. Do not commit, push, delete user data, or enable production services without explicit approval.

**Goal:** Make the existing local-model mode genuinely usable through Ollama so signed-in free users receive a bounded detailed-analysis trial and paid users receive a larger local quota while platform API and BYOK remain separate choices.

**Architecture:** Keep the existing `api_key_mode=local` and `ai_local` quota bucket. Add one DSA-owned Ollama runtime service for configuration, model selection, reachability and safe diagnostics; route fast and deep requests to separately configured models without falling back to paid providers; expose a secret-free status API and bilingual UI state. Guest quote lookup remains no-AI. Generated content is constrained to information and data, with no buy/sell instruction, target price, position sizing or return promise.

**Tech Stack:** Python 3.12, FastAPI, LiteLLM, Ollama OpenAI-compatible API, React, TypeScript, unittest, Vitest, Playwright.

---

### Task 1: Runtime contract and quota policy

**Files:**
- Create: `src/services/ollama_runtime_service.py`
- Modify: `src/platform_feature_policy.py`
- Modify: `.env.example`
- Test: `tests/test_ollama_runtime_service_v107.py`
- Test: `tests/test_platform_feature_policy.py`

- [ ] Add failing tests for disabled, unreachable, ready, missing-model and fast/deep model-selection states.
- [ ] Require local mode to use an Ollama-prefixed model, configured base URL, no external fallback models and a bounded concurrency gate.
- [x] Keep free and paid local quotas separate from platform API and BYOK buckets; paid limits must exceed free limits.
- [ ] Document optional local settings without embedding secrets or machine-specific paths.

### Task 2: Analysis routing and information-only guardrail

**Files:**
- Modify: `src/services/analysis_service.py`
- Modify: `src/analyzer.py`
- Modify: `api/v1/endpoints/analysis.py`
- Test: `tests/test_platform_ollama_analysis_v107.py`

- [ ] Add failing tests proving fast/deep requests select the configured quick/deep model.
- [x] Prevent local analysis from falling back to paid remote models when Ollama fails.
- [x] Return stable `local_model_disabled`, `local_model_unreachable`, `local_model_missing_model`, `local_model_busy` and timeout errors.
- [x] Append an information-only prompt guardrail in Chinese/English, neutralize action fields before persistence, and mask legacy Ollama reports on read without deleting stored data.
- [x] Release quota reservations when a synchronous local request fails before producing a report.

### Task 3: Secret-free local model status API

**Files:**
- Modify: `api/v1/endpoints/platform.py`
- Test: `tests/test_platform_ollama_status_api_v107.py`

- [ ] Add a public read-only status endpoint that exposes enabled/reachable/ready, configured model labels, availability and concurrency without environment values, paths, prompts or keys.
- [ ] Local mode remains login-required for AI execution even though status is readable.
- [ ] Return bilingual-safe reason codes for the frontend to localize.

### Task 4: Free-user retention UI

**Files:**
- Modify: `apps/dsa-web/src/api/platform.ts`
- Modify: `apps/dsa-web/src/pages/HomePage.tsx`
- Modify: `apps/dsa-web/src/i18n/uiText.ts`
- Test: `apps/dsa-web/src/api/__tests__/platform.test.ts`
- Test: `apps/dsa-web/src/pages/__tests__/HomePage.test.tsx`

- [ ] Add failing tests for ready, disabled, unreachable, exhausted and busy local-model states.
- [x] Show local model readiness, selected fast/deep lane, weekly remaining quota and information-only boundary near the mode selector.
- [ ] Disable local AI submission when unavailable while preserving free quote/query controls.
- [ ] Keep Chinese mode fully Chinese and English mode fully English except product/model proper names.

### Task 5: Deterministic and live acceptance

**Files:**
- Create: `scripts/verify_platform_ollama_local_retention_v107.py`
- Create: `tests/test_platform_ollama_local_retention_v107_verifier.py`
- Modify: `scripts/verify_platform_release_candidate_package.py`
- Modify: `tests/test_platform_release_candidate_package.py`
- Modify: `docs/CHANGELOG.md`
- Modify: `docs/superpowers/platform-product-rules.md`
- Modify: `docs/superpowers/platform-local-v1-acceptance-status.md`
- Modify: `docs/superpowers/platform-review-slices.md`
- Modify: `docs/superpowers/platform-release-candidate-manifest.md`

- [ ] Verify focused backend and frontend tests, build, release-package coverage and the V107 marker.
- [ ] Run a direct Ollama probe and one real local quick analysis plus one deep-model readiness check.
- [ ] Restart `8018`, then browser-test Chinese and English local-mode states across A-share and US symbols.
- [x] Confirm no secret exposure, no investment-advice wording, no remote paid fallback, independent quota accounting and no horizontal overflow.
- [ ] Run independent code review, `git diff --check`, sensitive-data scan and final dirty-tree inventory without committing.

Acceptance marker: `DSA_PLATFORM_OLLAMA_LOCAL_RETENTION_V107_OK`.

Boundary: local development only. No real payment, production deployment, production key, cloud model spend, legal approval or market-data redistribution approval is implied.

# DSA V58 Local Kronos Sandbox

Status: completed local-only implementation.

Boundaries:
- No-go for production deployment, real payment, real merchant keys, DNS, HTTPS, WAF, or public launch.
- Do not commit real API Key or production secret.
- Do not delete history reports, SQLite databases, user accounts, watchlists, or local cache data.
- Kronos model execution is opt-in local sandbox only. It must require `KRONOS_ENABLED=true`, local dependencies, local model availability, and premium/local-model permission.
- If Kronos dependencies are missing, return `model_unavailable` and a local rules fallback. Do not claim the Kronos model ran.
- No AI calls and no public search are allowed in the fallback path.
- All forecast output is experimental information analysis only; not investment advice.

Target:
- Add a deterministic `/api/v1/stocks/{code}/kronos-forecast` endpoint.
- Add runtime dependency probing for `torch`, `einops`, `safetensors`, `huggingface_hub`, and Kronos `model`.
- Add cache, timeout/concurrency guard, prediction record JSONL, and lightweight backtest summary.
- Add frontend controls that clearly separate local rules preview from real Kronos model status.
- Add verifier marker `DSA_PLATFORM_KRONOS_SANDBOX_V58_OK`.

Implemented:
- `src/services/kronos_forecast_service.py`
- `GET /api/v1/stocks/{code}/kronos-forecast`
- HomePage `basic-query-kronos-*` sandbox panel
- Backend, frontend, verifier, and release package tests

Local expected runtime:
- If `torch`, `einops`, `safetensors`, `huggingface_hub`, or Kronos `model` are missing, the endpoint returns `model_unavailable`, `kronos_model_used=false`, and local fallback scenarios.
- Real Kronos execution remains opt-in with `KRONOS_ENABLED=true` and local dependency/model availability.

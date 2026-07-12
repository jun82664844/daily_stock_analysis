# DSA V108 Kronos RTX 5090 Runtime

## Objective

Turn the existing Kronos sandbox from an installed but disabled adapter into a
measurable local runtime on the RTX 5090. The feature remains experimental
market-data analysis. It must not emit trading instructions, target prices, or
investment advice.

## Product boundary

- Anonymous and free snapshot requests keep the local-rules preview and must
  not consume the real Kronos runtime.
- A real model run requires an eligible local platform identity and an explicit
  `require_model=true` request.
- `kronos_model_used=true` is returned only after the model produced forecast
  rows successfully.
- Missing data, disabled runtime, dependency failures, concurrency limits, and
  timeouts fall back honestly or return the existing explicit model-unavailable
  response when the caller required the model.

## Engineering scope

1. Cache the Kronos model and tokenizer once per model/device/context key.
2. Prefer the already downloaded Hugging Face cache and support offline-only
   model loading.
3. Report resolved device, model cache hit, model load time, inference time,
   peak allocated VRAM, input bars, and output bars.
4. Keep concurrency at one by default and preserve timeout fallback behavior.
5. Verify A-share, US, and Hong Kong symbols on the RTX 5090.
6. Show runtime evidence in Chinese and English without presenting model output
   as advice.

## Acceptance

- Unit and API tests cover access boundaries, runtime caching, metrics, real
  success, timeout/error fallback, and secret-free records.
- Live local runs for `600519.SH`, `AAPL`, and `0700.HK` report
  `kronos_model_used=true` only on successful inference.
- The acceptance log records latency and VRAM without recording credentials or
  user data.
- Browser checks cover Chinese and English states and preserve the information-
  only disclaimer.
- Release-package, sensitive-data, whitespace, and Git-state checks pass.

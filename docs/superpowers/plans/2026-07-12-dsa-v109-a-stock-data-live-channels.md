# DSA V109 a-stock-data Live A-share Channels

## Objective

Enable the installed a-stock-data reference adapter for local A-share queries
without turning unofficial public endpoints into an unlimited public backend.

## Scope

- Move the pinned upstream checkout to `external/a-stock-data` inside the DSA
  project and remove the old C-drive default path.
- Enable CNINFO announcements, Eastmoney concept blocks, reports, fund flow,
  and dragon-tiger checks for the local runtime.
- Fall back from intraday fund flow to recent daily history when the minute
  endpoint is empty.
- Apply a process-wide Eastmoney request-start interval, shared cache, total
  request budget, per-channel timeout, and honest per-channel degradation.
- Preserve no-AI, no-public-search, information-and-data-only boundaries.

## Acceptance

- Pinned upstream commit: `bcda4054b979166a3d06b628f16f3dc9b1ff7eb2`.
- `600519.SH` completes all five channel checks within the configured local
  budget; empty or blocked fund-flow endpoints remain visibly degraded.
- Tests cover daily fund-flow fallback, global request pacing, local external
  path, cache, timeout, and structured channel details.
- Existing A-share UI, Chinese/English copy, release package, sensitive-data
  scan, and local operability checks remain green.

All output is information and data only. It is not investment advice and does
not include trade instructions, positions, target prices, or return promises.

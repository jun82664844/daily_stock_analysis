# DSA V71 Free Multimarket Modules

## Objective

Keep the free local query experience useful across A-share, US equity, HK equity, and crypto routes even when the backend only returns a basic no-AI snapshot.

## Scope

- local-only
- No-go for production deployment
- No real payment
- No production secrets
- No AI calls
- No public search
- Do not commit real API Key
- Do not delete history reports, user accounts, or local databases
- All analysis is information analysis only and is not investment advice

## Product Rule

Free users and premium users should see the same visible modules first. Premium/API modes may later improve freshness, source depth, model output, and persistence, but the free page must not feel empty.

## V71 Deliverables

- free multimarket modules for A-share, US equity, HK equity, and crypto
- same visible modules for basic no-AI snapshots
- fallback peer comparison table when backend peer data is unavailable
- fallback K-line triggers when Kronos or model forecast data is unavailable
- localized backend comparison targets when live data already provides English peer labels or reasons
- market-specific labels and peers:
  - A-share: 沪深300 / 上证指数
  - US equity: Nasdaq Composite / Technology sector ETF
  - HK equity: Hang Seng Index / Tracker Fund of Hong Kong
  - crypto: Ethereum / Bitcoin
- verifier marker: DSA_PLATFORM_FREE_MULTIMARKET_V71_OK

## Verification

- `npm.cmd run test -- HomePage.test.tsx --reporter=dot`
- `npm.cmd run build`
- `python -m unittest tests.test_platform_free_multimarket_v71 tests.test_platform_release_candidate_package`
- `python scripts/verify_platform_free_multimarket_v71.py`
- `python scripts/verify_platform_release_candidate_package.py`
- browser smoke at `http://127.0.0.1:8018/?dsa_v71_browser=1`

## Browser Evidence Targets

- `600519.SH`: A股重点数据 + 沪深300
- `AAPL`: 美股重点数据 + 纳斯达克综合指数
- `00700.HK`: 港股重点数据 + 恒生指数, no English peer label leakage in Chinese mode
- `BTC-USD`: 加密货币重点数据 + 以太坊, no English peer label leakage in Chinese mode

## Acceptance

`DSA_PLATFORM_FREE_MULTIMARKET_V71_OK` is printed only when the implementation, tests, docs, release package coverage, and `.gitignore` visibility are all present.

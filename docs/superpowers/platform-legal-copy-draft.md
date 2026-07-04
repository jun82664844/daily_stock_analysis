# DSA Platform Legal Copy Draft

Date: 2026-07-01

Status: draft for product/legal review. This is not final legal advice and must be approved before public launch.

## Not investment advice

DSA provides market data organization, model-assisted research, and historical analysis views for information only. Outputs are not investment advice, securities recommendations, trading instructions, or guarantees of future performance. Users remain responsible for their own decisions and should consult qualified professionals where appropriate.

## Privacy

The platform may store account email, authentication metadata, selected plan, quota usage, analysis requests, analysis history, audit events, and operational diagnostics needed to run the service. Production launch requires a final privacy policy that defines retention periods, deletion/export processes, support access controls, and incident notification rules.

## API Key custody

When a user stores an API key, DSA should encrypt it at rest, avoid returning plaintext through APIs, avoid rendering it in the frontend, and redact it from audit logs and diagnostics. Operators should not ask users to send API keys through chat, screenshots, email, or support tickets. Production launch requires key rotation and deletion workflows.

## BYOK risk notice

BYOK means the user chooses to use their own model provider credentials. The external provider may charge the user directly, apply its own rate limits, log requests under its own policy, or reject requests based on region, model access, account status, or safety rules. DSA should explain that BYOK usage is separate from platform model cost accounting but still subject to platform abuse-control quota.

## Quota and plan copy

Free users can use basic no-AI queries and limited quick AI analysis. Pro users receive higher platform API limits. Enterprise limits may be unlimited or contract-defined. BYOK and local model modes use separate quota buckets for abuse control and capacity protection. Final pricing, quota numbers, paid plan names, refund policy, and upgrade flow require manual business approval.

## Product safety copy

- Reports are historical snapshots or current data summaries depending on the screen and data freshness.
- Prices, indicators, news, and fundamentals may be delayed, incomplete, estimated, or unavailable.
- Model output may be wrong, stale, incomplete, or inconsistent with later market information.
- Users should not rely on DSA as the sole basis for trading or investment decisions.

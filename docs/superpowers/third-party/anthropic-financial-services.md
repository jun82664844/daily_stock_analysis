# Anthropic Financial Services Local Reference

## Source

- Repository: `https://github.com/anthropics/financial-services.git`
- Local checkout: `external/anthropic-financial-services`
- Accepted commit: `4aa51ed3d379731f8f9beff498d749580372699c`
- Runtime diagnostics report the source as installed only when this exact commit, Apache-2.0 license text, and all four allowlisted skill files are present.
- License: Apache-2.0

The checkout is ignored by the DSA Git repository. DSA records attribution and its own adapter code, but does not vendor the full external repository into a DSA commit.

## Enabled scope

DSA reads only the presence and source references of these four allowlisted skills:

- `financial-analysis/skills/comps-analysis`
- `equity-research/skills/earnings-analysis`
- `equity-research/skills/sector-overview`
- `equity-research/skills/catalyst-calendar`

DSA does not import or execute the external Python, shell, PowerShell, JavaScript, command, agent, or MCP files. Research facts come from the existing DSA no-AI stock snapshot.

## Disabled scope

- Claude Cowork and Claude Managed Agents are not deployed.
- Anthropic API access is not configured by this integration.
- External MCP connectors, including subscription data providers, are disabled.
- Investment-banking, private-equity, wealth-management, KYC, accounting, and transaction workflows are not exposed.
- The external repository is a research-method reference, not a market-data license or permission to redistribute provider data.

## Local install and update

Initial install:

```powershell
git clone --depth 1 https://github.com/anthropics/financial-services.git external\anthropic-financial-services
```

Review a future update before changing the accepted commit:

```powershell
git -C external\anthropic-financial-services fetch --depth 1 origin main
git -C external\anthropic-financial-services log -1 --oneline origin/main
```

Do not update automatically. Re-run the V106 verifier and browser acceptance after any source revision change.

## Configuration and rollback

`DSA_FINANCIAL_SERVICES_ROOT` may point to another local checkout. When unset, DSA uses `external/anthropic-financial-services` under the project root.

Rollback is non-destructive to user data: remove or rename the ignored external checkout, or point `DSA_FINANCIAL_SERVICES_ROOT` at an unavailable directory. The research page will retain DSA facts and report the reference source as unavailable. No report, account, database, API key, or watchlist is deleted.

All V106 output provides information and data only. It does not provide investment advice, trading instructions, target prices, or return forecasts.

# DSA Local V15 User Query Loop

Date: 2026-07-03
Scope: local functional upgrade only.

## Goal

Make the ordinary-user query path understandable and verifiable in the local app:

- show the signed-in user, plan, weekly free quota, BYOK readiness, and recommended query mode on the Home page;
- keep quick snapshot queries explicitly no-AI and separate from stored historical reports;
- show the routed market lane for A shares, US stocks, HK stocks, and crypto quick snapshots;
- warn that quick/deep AI analysis can consume platform, BYOK, or local-model quota depending on the selected mode;
- add a V15 verifier with an explicit `DSA_PLATFORM_LOCAL_USER_QUERY_LOOP_V15_OK` marker.

## Boundaries

- No production deployment, domain, HTTPS, WAF, cloud migration, real payment, merchant account, or production secret work.
- No real API Key usage in tests, docs, or verifier output.
- No deletion of historical reports, databases, user data, or static build outputs.
- No `git add`, `git commit`, or `git push`.
- Sandbox billing remains local mock only.
- Analysis output remains information analysis only and is not investment advice.

## Acceptance

- HomePage tests cover platform account summary, masked BYOK status, no-AI quick query status, route lane, current-vs-history copy, and AI quota-cost warning.
- V15 verifier checks required files, verifier visibility, focused frontend tests, V14 compatibility without live browser overreach, and no-AI market-lane payload shape.
- Release candidate package verifier includes V15 files in required-file, visibility, dirty-inventory, and manifest coverage checks.
- Final validation reports dirty-tree counts and keeps all上线前事项 as no-go.

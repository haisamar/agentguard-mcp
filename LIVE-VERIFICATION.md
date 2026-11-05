# AgentGuard live verification

Verified November 3, 2026 (America/Toronto).

Frontend: https://agentguard-eight.vercel.app
MCP endpoint: https://agentguard-mcp-wine.vercel.app/mcp
Backend release tested: b8e25d3 (includes safety fixes published earlier).

## Observed results

1. Sales Agent requested a $750 refund: rejected for missing finance:refund scope.
2. Finance Agent requested a negative refund: DENY; invalid amount.
3. Finance Agent requested a $751 refund: APPROVAL_REQUIRED; persisted as PENDING.
4. Finance Agent attempted execution while PENDING: DENY.
5. User approved the labeled verification request in the authenticated dashboard. Database read-back confirmed APPROVED and a human reviewer identity.
6. Original Finance Agent executed the approved request: ALLOW, simulated refund_processed result.
7. Original Finance Agent retried the same approval: DENY, already executed.

Reference: apr_1beb6d3a46. The request reason explicitly marks it as verification data. No payment provider is integrated and no real money was transferred.

## Scope and limits

These checks used actual deployed services, real Auth0 machine credentials, a human dashboard approval, and persisted Supabase records. They establish the listed observations only. They do not prove exactly-once external payment effects, simultaneous replay protection under load, expiry behavior, wrong-identity rejection in the live environment, or broad resistance to arbitrary attacks. The public walkthrough remains scripted.

The separate automated handler regression suite contains 12 passing tests with mocked storage. Do not combine that count with these observations into a security success-rate claim.

Raw local evidence is retained separately and contains identity identifiers; it is not included in this public summary.

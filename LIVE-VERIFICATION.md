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


## Additional deployed-service checks (November 4, 2026 client date)

Using synthetic preapproved database fixtures explicitly labeled as test-harness data (not human decisions), the deployed backend denied execution for a mismatched requester and a request older than two hours. Eight concurrent execution requests against one fresh fixture returned one ALLOW and seven DENY results. This is a single eight-request trial of simulated execution, not proof of exactly-once external payment effects or a broad load test.

A proposed SQL migration in database/migrations/001_refund_receipts.sql adds a sandbox receipt ledger and atomic execution RPC. It is not yet applied, database-tested, or connected to the running application. Do not present receipts as a live feature until migration and integration verification complete.


## Receipt transaction database verification

The receipt migration is now applied to AgentGuard. The backend-only RPC uses a row lock and writes the sandbox receipt, EXECUTED status and success audit event in one PostgreSQL transaction. Browser-role execute grants were checked and are absent.

A direct database API trial with synthetic preapproved fixtures submitted eight concurrent calls: one ALLOW, seven DENY, exactly one receipt for 75100 USD minor units. Wrong-identity, expired and invalid-precision cases were denied and produced no additional receipts. These are database tests, not human-review evidence or external payment tests.

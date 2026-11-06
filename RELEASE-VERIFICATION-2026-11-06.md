# Deployed safety release — November 6, 2026

AgentGuard only. Synthetic USD ledger; no real payment is sent.

## Exact deployed revisions

- Frontend: `5c469b4234451fb192c8692113bb0e8ceaf26f74`, deployment
  `dpl_AKXdPaPSYDmeCmXr3QddQY3BVSs4` (READY).
- Backend: `65c3633fdbf1e3b43df9b17eb5a4946ef03a409b`, deployment
  `dpl_Ckvwqf3oXaVfz4JqnRyoADUhbjo2` (READY).
- AgentGuard database migrations 001–008 installed. Migration 008 evaluates
  approval expiry after obtaining the row lock; audit-failure rollback passed.
- Frontend: https://agentguard-eight.vercel.app
- MCP: https://agentguard-mcp-wine.vercel.app/mcp
- Previous rollout baselines: frontend `dpl_HgDv2jNnFrq1UZPYkywqBGADbrpQ`,
  backend `dpl_DXguhEuiSQvpYgCi5KHbJAMyS4b5`.

## Observed checks

Seven frontend tests, lint, TypeScript and default Turbopack production build
passed. Twenty-two backend tests and dependency-lock consistency passed.

Twenty-two live probe assertions passed with real existing Auth0 machine tokens:
public liveness/metadata, missing and invalid token rejection, v2 tool schema,
CRM read permission, Sales refund denial, one-cent execution, identical retry,
changed-payload denial, review requirement, machine approval denial, pending
execution denial, human-approved execution, replay denial, pause state, paused
execution rejection without partial request, cancellation denial, and resume.

The owner directly approved synthetic request
`apr_c7d535f43fe3410eaa154ce583e5fa4d` after passkey reauthentication. Execution
created exactly one simulated 75500-cent receipt
`dcd9e936-92e9-479e-9f6e-a68ab38daaa6`; replay was denied. Database inspection
confirmed one human-review audit event and one receipt.

Cancellation and pause/resume were agent-operated through the signed-in human
administrator's browser, not through MCP approval tools. Cancellation left zero
receipts and one cancellation audit. Resume succeeded after owner-controlled fresh
passkey authentication. Final database and dashboard state: execution enabled.

Sanitized results: `evidence/deployed-release-2026-11-06.json`. Local probe sources
are under the workspace `.verification` directory; a portable versioned evaluation
runner and fresh-checkout/database rehearsal are still needed. This record does
not claim that every live assertion is already reproducible from this repo alone.

## Reliability finding and limits

An observed dashboard failure was Supabase HTTP 401/PGRST303, `JWT issued at
future`. Retry recovered the dashboard. Frontend revision 5c469b4 adds at most
three GET attempts for this exact error and temporary service HTTP statuses;
invalid credentials/permission denial fail immediately. No write is retried and
no verification or authorization is disabled. Raw database errors are omitted
from new read errors. Fault tests cover recovery, immediate authorization failure,
and bounded service failure. Provider clock behavior remains external.

Passkeys use Auth0 Free; no paid upgrade occurred. The first enrollment callback
had an unconfirmed error despite Auth0 reporting a successful token exchange;
subsequent fresh passkey sign-ins and sensitive actions succeeded.

Non-admin/stale authentication negative cases are currently policy tests, not a
complete live-browser matrix. Signed wrong-issuer/audience/expired-token tests,
full public website/demo review, fresh database rehearsal, broader evaluation,
and video remain open. Database/service administrators are trusted. This is
neither an immutable audit guarantee nor real payment-provider integration.

# AgentGuard submission evidence and release gates

## Demonstrated

- Actual deployed Auth0 machine identity and scope checks.
- Human review in the authenticated dashboard.
- Expiring approval bound to the requesting identity.
- One sandbox receipt, execution state and success audit event written atomically.
- Live sequential replay denied; one eight-request concurrency trial produced one receipt.
- Wrong identity, expiry and invalid precision denied.
- Intentional audit insert failure rolled back the receipt and execution update in PostgreSQL. The test trigger and fixtures were rolled back.
- Missing/malformed authentication returned 400; invalid and signature-tampered tokens returned 401. A tampered-token test does not independently prove rejection of a correctly signed wrong-audience token.

## Limitations that must remain visible

Refunds are simulated USD ledger entries. No payment-provider integration exists. A compromised backend service credential or privileged database administrator is outside the protection boundary. Audit history is persisted, not cryptographically immutable. The $500 autonomous threshold is per request: splitting refunds to remain below the threshold is not covered by a cumulative spending limit. Below-threshold simulated refunds do not yet use the approved-action receipt transaction. Public demo animations are scripted. Fourteen handler/policy tests use mocked storage; do not report them as live security trials.

## Video script (2–3 minutes; recording outstanding)

1. Explain the concrete risk: an agent issuing a high-impact refund without independent authority.
2. Show the trust boundary: Auth0 identity -> scope -> policy -> separate human review -> transaction ledger.
3. Show Sales Agent denied and Finance Agent high-risk request held.
4. Show an actual human dashboard approval and the receipt from the original agent.
5. Show replay denial, the eight-request trial result, and the linked audit record.
6. State the simulated-payment scope, per-request threshold limitation and reproducibility links.

Use synthetic identities and redact secrets/personal identifiers. Do not stage prerecorded animations as live enforcement. Record against a named frontend/backend release SHA.

## Remaining release gates

- Visual browser verification of receipt layout, mobile/keyboard behavior and verified-admin sign-in.
- Independently signed expired/wrong-issuer/wrong-audience tokens and non-admin user session tests.
- Fresh-clone setup using only the published instructions and schema migrations.
- Review Supabase availability/plan and recovery arrangements through judging; no availability guarantee has been established.
- A real video artifact and working reviewer links.
- A sandbox baseline comparison and machine-readable evaluation runner/results.
- Review how cumulative spending limits and payload immutability should be enforced before claiming protection against refund splitting or privileged payload edits.

Do not mark these gates complete based on this document.

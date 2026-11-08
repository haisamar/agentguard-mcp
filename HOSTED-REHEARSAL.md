# Rehearse AgentGuard on fresh hosted services

Use an isolated AgentGuard rehearsal environment with synthetic data. The local
evaluator already checks the schema and migrations from empty PostgreSQL; this
procedure additionally checks the providers, browser sessions, and permissions.
It has not yet been run on a fresh hosted environment.

## Prepare the rehearsal

1. Record the frontend and backend commit SHAs. Use Node 24 and Python 3.12.
   Run `npm ci && npm test && npm run build` in the frontend and run the backend
   test suite from its locked dependencies. Run `evaluation/README.md`'s local
   check before provisioning anything.
2. Use a separate, empty AgentGuard Supabase database. Confirm the project URL
   differs from the live project before applying SQL. Apply `database/schema.sql`
   and then `database/migrations/001` through `008` in filename order. Do not copy
   production data. A branch cloned from production schema can test integration,
   but is not a proof of installation from an empty hosted database.
3. Verify actual PostgREST grants as well as RLS. Anonymous and authenticated
   roles must not read these private tables or call the privileged RPCs. The
   server role needs reads of approvals/audits and insert access for audit events
   in addition to the grants in the numbered migrations. If those base grants
   are absent, grant only `SELECT` on `public.approvals, public.audit_events` and
   `INSERT` on `public.audit_events` to `service_role`. Verify direct table access
   and RPCs with the rehearsal project's key. Keep the key server-side.
4. In an isolated AgentGuard Auth0 configuration, create a regular web app and
   an RS256 API. Create scoped Sales, Finance, and machine-admin clients. Grant
   Sales `crm:read`, Finance `crm:read` and `finance:refund`, and machine admin
   `agent:manage`. Register the exact frontend `/auth/callback` and logout
   origin. Configure a verified human account and pin its exact session subject
   and email. Update the Action's client and connection IDs for this environment
   before binding it to Post Login; keep the claim name consistent with the web
   verifier. The operator enrolls and uses their own passkey.
5. Deploy to scoped rehearsal targets. The web target needs `AUTH0_DOMAIN`,
   `AUTH0_CLIENT_ID`, `AUTH0_CLIENT_SECRET`, `AUTH0_SECRET`, `APP_BASE_URL`,
   `AGENTGUARD_ADMIN_EMAIL`, `AGENTGUARD_ADMIN_SUB`, `SUPABASE_URL`, and
   `SUPABASE_SECRET_KEY`. Use a unique session encryption secret. The MCP target
   needs the variables listed in [DEPLOYMENT.md](DEPLOYMENT.md). Use the rehearsal
   URLs, API identifier and credentials only. Keep deployment protection in
   place and use an authenticated preview session if required.

## Verify and record

- Confirm anonymous demo access, logged-out dashboard redirect, and a verified
  non-admin's rejection. Confirm the pinned admin can sign in, but approval and
  resume reject a password-only or stale session.
- Use the deployed `/mcp` with test machine tokens: Sales can search and cannot
  refund; Finance can submit; machine admin cannot approve. Attempt execution
  before human review, then approve one synthetic request with a fresh passkey.
  Verify one exact simulated receipt and replay denial. Verify pause blocks new
  effects, resume restores them, and cancellation leaves zero receipts.
- Save the environment type, exact builds, migration set, and sanitized outcomes.
  Verify the live AgentGuard environment was unchanged. Retire rehearsal resources
  according to their owning account's policy and record any remaining costs.

AgentGuard had no existing Supabase rehearsal branch when checked. Supabase
[preview branches incur usage charges](https://supabase.com/docs/guides/platform/manage-your-usage/branching).
Check account entitlements and explicit spend authorization before creating a
billable environment. If a free, isolated target is unavailable, retain the
local and existing deployment evidence and report the hosted rehearsal as open.
For authentication configuration, see the [Auth0 Next.js SDK guide](https://auth0.github.io/nextjs-auth0/).

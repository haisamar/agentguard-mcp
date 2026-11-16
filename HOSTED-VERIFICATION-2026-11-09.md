# Hosted AgentGuard rehearsal — November 9, 2026

Recorded from the completed rehearsal. The application uses a simulated USD
ledger. The public demo and the local baseline evaluation have separate evidence.

## Revisions and environment

- Frontend source `04e659debaee714d5987e278025646ce155e53d2`, protected preview
  deployment `dpl_2JukDFVyGHnG9nxJ5NmdoHjYn3ua`.
- MCP source `99c2c7be98920b8dc4aae8d69b9568aef1bb8542`, protected preview
  deployment `dpl_9r3NbD4XYivmxTchndyAETuLjXMq`.
- Separate Auth0 dashboard client, RS256 API audience, finance-scoped test
  client, and a passkey Action restricted to that rehearsal client.
- Separate Supabase database on PostgreSQL 17.11. Installed `database/schema.sql`
  then migrations 001–008 into an empty project. All seven files under
  `database/tests/` passed, with their transactions rolled back.

## Observed workflow

1. A real Auth0 sign-in reached the protected rehearsal dashboard. The account
   was denied while its identity differed from the configured administrator.
2. After the verified account was pinned in rehearsal, it could load dashboard
   data from the separate hosted database.
3. The finance-scoped test client submitted request
   `apr_0c11140854a24923917bb08cdcb89f84` for 75800 USD minor units to `acct_001`.
   It remained PENDING with zero receipts. Execution before approval was denied.
4. The owner approved that request after passkey reauthentication.
5. The original client executed the approved transaction. Supabase read-back
   confirmed EXECUTED, a human reviewer, exactly one receipt, and exactly 75800
   cents for the same requester, destination, and currency. Replay was denied.
6. Production had no matching request, and production execution remained enabled.
   The temporary rehearsal automation bypass was revoked and the local probe
   stopped. Preview protection remained enabled.

## Database recovery and permissions

Anonymous Data API access returned no approval rows and denied a privileged
pause RPC with HTTP 401. The `anon` and `authenticated` roles lacked execute
grants on privileged RPCs. A transaction run under `service_role` independently
verified pending execution denial, wrong-requester denial, one authorized
receipt, and replay denial, then rolled back its synthetic data.

The empty rehearsal project was paused and restored through Supabase. Its API
stopped resolving while inactive and responded after restoration. The review
function and enabled execution state survived. Production public checks passed
during the drill. These tests preceded the persisted human-approved request.

## Scope

This was one end-to-end hosted rehearsal with a real human approval. The access
test used the same account before and after pinning it in rehearsal. A distinct
verified non-admin account was not used against production. The database role
trial used a synthetic reviewer and is separate from the real approval above.
The walkthrough uses fixtures, and the local comparison uses ten fixed cases.
The project trusts Auth0 and privileged backend/database operators.

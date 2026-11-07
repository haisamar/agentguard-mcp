# Reproduce the local ledger comparison

From a checkout of the AgentGuard MCP repository, use Node.js 24 or newer:

```sh
cd evaluation
npm ci --ignore-scripts
npm run --silent evaluate
```

Installation needs access to npm. The run uses a pinned [PGlite](https://pglite.dev/docs/) PostgreSQL build in memory. It does not read `.env`, connect to any hosted service, run an agent model, or move real money. It creates local roles, loads `database/schema.sql` and the numbered migrations from this checkout, runs the rollback-only SQL assertion files, and checks receipt count and total integer cents after each scenario. A mismatch exits unsuccessfully. Every scenario starts from an empty ledger.

The same scenario operations are applied to three implementations:

- **Unguarded:** records submitted refunds and permits repeat execution.
- **Scope and threshold:** checks the fixture agent’s refund permission and requires review above $500. It lacks shared budget accounting, request deduplication, approval identity binding, replay protection, cancellation and pause.
- **AgentGuard database:** applies actual request, review, execution and control functions from the migrations. The runner supplies trusted synthetic actors and models the scope check outside SQL; it does not test Auth0 or the MCP transport here.

Counts are descriptive results for this fixed sample, not a statistically representative score. The two intentionally limited baselines are illustrative local models. All effects are simulated. An in-memory single connection cannot establish production concurrency or hosted service configuration. See the transport tests, the separate live release report, and the opt-in concurrency probe for those distinct types of evidence. This is a fresh database schema rehearsal, not a fresh Supabase/Auth0 integration rehearsal.

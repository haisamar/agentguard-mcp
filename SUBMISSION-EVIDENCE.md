# AgentGuard submission evidence

Start with the [public walkthrough](https://agentguard-eight.vercel.app/demo)
and the [evidence page](https://agentguard-eight.vercel.app/evidence). Both open
without an account. The public walkthrough uses a guided simulation.

| Evidence | Result and scope |
| --- | --- |
| [November 6 hosted report](RELEASE-VERIFICATION-2026-11-06.md) | 22 checks on named deployments. A human reviewed a $755 simulated refund after passkey sign-in. The original agent created one receipt. Replay was denied. Cancellation and pause/resume were also observed. |
| [November 5 database concurrency report](evidence/request-integrity-2026-11-05.json) | Eight identical concurrent submissions produced one receipt in one case and one pending approval in another. This was one trial per case through the database API. |
| [Local evaluator](evaluation/README.md) | Empty PostgreSQL setup and seven SQL assertion files. On ten fixed cases, AgentGuard matched expected receipt effects 10 times, the scope-and-threshold baseline 3 times, and the unguarded baseline once. This runner uses one connection and synthetic identities. |
| [Administrator verification](https://github.com/haisamar/agentguard/blob/main/ADMIN-SECURITY.md) | The local production frontend denied signed-out, wrong-subject, and unverified dashboard requests. All ten direct approval and resume attempts under disallowed session conditions stopped before a write. This used encrypted Auth0 SDK fixture sessions. |

## Pinned runtime source

- [Frontend `cd7c263`](https://github.com/haisamar/agentguard/commit/cd7c263092faff19a4166fcfcff7718bee1c0233)
- [MCP backend `807aee6`](https://github.com/haisamar/agentguard-mcp/commit/807aee629b81b9d8ebb3ce09c300fbec043a1106)

The hosted approval report identifies the earlier builds used in that run.
Later runtime checks include signed-out public access, local dashboard access
tests against the pinned frontend, and a read-only live machine-token smoke test.

## Limits and open checks

- All refunds are simulated USD ledger entries. The trusted backend credentials
  and privileged database administrators sit inside the trust boundary.
- The local evaluation compares fixed ledger cases. It does not measure model
  behavior. The separate concurrency trial is limited to the documented cases.
- The full negative live Auth0 browser matrix and an empty hosted installation
  remain open. See the [rehearsal guide](HOSTED-REHEARSAL.md).

The [recording script](VIDEO-SCRIPT.md) uses the public walkthrough and the
dated evidence. See the [November 3–4 checkpoints](LIVE-VERIFICATION.md) for
earlier results.

## Historical fresh-checkout check (November 5, 2026)

Both repositories were cloned from GitHub without copying local environment files. The frontend npm ci and lint completed successfully. The backend installed published requirements in a new Python 3.14 virtual environment and passed all 14 tests using dummy database configuration. This does not constitute a production Python 3.12 fresh-install verification or a complete judge setup rehearsal. Frontend dependency audit surfaced advisories and initiated a patched-framework release; final audit/build results must be recorded after verification.

The later evidence includes a clean Python 3.12 installation and empty local
database run. See [dependency verification](DEPENDENCIES.md) for the dated scan.

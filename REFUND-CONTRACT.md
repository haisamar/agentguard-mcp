# Refund request contract v2

Local implementation uses `issue_refund(request_id, account_id, amount_minor,
currency, reason)`. Identity comes from the verified token, never tool arguments.

Example arguments:

```json
{"request_id":"refund_order_123","account_id":"acct_001","amount_minor":75100,"currency":"USD","reason":"Approved customer refund request"}
```

Use a stable request ID (1–128 ASCII letters, digits, underscores or hyphens) for
the same operation, including retries after timeouts. Amount is a positive integer
number of cents, up to 99999999999900. Booleans, strings and fractional cents are
rejected. Currency is USD; allowed accounts are acct_001, acct_002 and acct_003.
Reason must contain non-whitespace text and be at most 2000 characters.

Within one authenticated identity, identical submissions return the original
submission result without another receipt or pending approval. Changed arguments
with the same ID are denied. A new ID denotes a new operation and still consumes
the shared budget. Other identities do not receive the first identity's result.

For pending requests, retry returns the original submission acknowledgement,
not an updated approval status. Human review and execute_approved_refund remain
separate steps. Approved execution remains single-use; repeats are denied.

The database serializes submission, budget check, receipt/approval, audit event,
and idempotency record in one transaction. Audit failures roll back the operation.
Idempotency records must not be deleted while retries must remain protected.

Legacy `amount` tool calls must migrate to `amount_minor` plus request ID and
currency; missing required fields produce a tool validation error. Historical
approval payloads remain readable. v2 approvals include a derived `amount` field
for the existing dashboard/execution reader, calculated exactly by PostgreSQL
from integer cents; callers cannot supply that derived value.

Migration 006 is installed in AgentGuard's database. MCP handler changes are
local until deployment; this document is not a claim that production uses v2.
All effects are simulated ledger entries, not external payment execution.

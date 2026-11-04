import asyncio
import json
from types import SimpleNamespace
import unittest
from unittest.mock import MagicMock, patch
from src.policy import evaluate, Decision
from src import approvals


class SafetyTests(unittest.TestCase):
    def test_mcp_cannot_grant_human_approval(self):
        from src import tools
        registered = {}
        class Registry:
            def tool(self, **options):
                def capture(fn):
                    registered[options["name"]] = fn
                    return fn
                return capture
        harness = SimpleNamespace(mcp=Registry(), register_scopes=lambda scopes: None)
        tools.register_tools(harness)
        ctx = SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(
            state=SimpleNamespace(auth={"extra": {"sub": "machine@clients"}}))))
        with patch.object(tools, "record_event") as audit:
            result = asyncio.run(registered["approve_action"].__wrapped__("apr_test", ctx))
            self.assertEqual(json.loads(result)["decision"], "DENY")
            self.assertEqual(audit.call_args.kwargs["metadata"]["security_event"], "approval_bypass_attempt")

    def test_invalid_amounts_are_denied(self):
        for amount in [None, True, False, 0, -1, "invalid", float("nan"), float("inf"), -float("inf")]:
            with self.subTest(amount=amount):
                self.assertEqual(evaluate("issue_refund", {"amount": amount})["decision"], Decision.DENY)

    def test_refund_threshold(self):
        self.assertEqual(evaluate("issue_refund", {"amount": 500})["decision"], Decision.ALLOW)
        self.assertEqual(evaluate("issue_refund", {"amount": 500.01})["decision"], Decision.APPROVAL_REQUIRED)

    def test_restricted_actions(self):
        self.assertEqual(evaluate("delete_customer", {})["decision"], Decision.DENY)
        self.assertEqual(evaluate("export_customer_data", {})["decision"], Decision.APPROVAL_REQUIRED)

    def test_lost_execution_claim_is_rejected(self):
        database = MagicMock()
        database.table.return_value.update.return_value.eq.return_value.eq.return_value.execute.return_value.data = []
        with patch.object(approvals, "supabase", database), patch.object(approvals, "get_approval", side_effect=AssertionError("must not reread a lost claim")):
            self.assertIsNone(approvals.mark_executed("apr_test"))


if __name__ == "__main__":
    unittest.main()

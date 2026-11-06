"""Tool-handler regression tests. Storage is mocked; no live transactions occur."""
from datetime import datetime, timezone
import asyncio
import json
import unittest
from types import SimpleNamespace
from unittest.mock import patch
from src import tools


class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.registered = {}
        registered = self.registered
        class Registry:
            def tool(self, **options):
                def capture(fn):
                    registered[options["name"]] = fn.__wrapped__
                    return fn
                return capture
        tools.register_tools(SimpleNamespace(mcp=Registry(), register_scopes=lambda scopes: None))
        self.ctx = SimpleNamespace(request_context=SimpleNamespace(request=SimpleNamespace(
            state=SimpleNamespace(auth={"extra": {"sub": "finance-agent"}}))))
        self.row = {"created_at": datetime.now(timezone.utc).isoformat(), "id": "apr_test", "identity": "finance-agent", "action": "issue_refund",
                    "status": "APPROVED", "approved_by": "human:reviewer",
                    "payload": {"account_id": "acct_001", "amount": 750, "reason": "test"}}

    def execute(self):
        return json.loads(asyncio.run(self.registered["execute_approved_refund"]("apr_test", self.ctx)))

    def test_denied_states_never_claim_execution(self):
        for status in ["PENDING", "DENIED", "EXECUTED"]:
            with self.subTest(status=status), patch.object(tools, "get_approval", return_value={**self.row, "status": status}), patch.object(tools, "execute_with_receipt") as claim, patch.object(tools, "record_event"):
                self.assertEqual(self.execute()["decision"], "DENY")
                claim.assert_not_called()

    def test_wrong_identity_and_action_never_claim(self):
        for change in [{"identity": "other-agent"}, {"action": "export_customer_data"}]:
            with self.subTest(change=change), patch.object(tools, "get_approval", return_value={**self.row, **change}), patch.object(tools, "execute_with_receipt") as claim, patch.object(tools, "record_event"):
                self.assertEqual(self.execute()["decision"], "DENY")
                claim.assert_not_called()

    def test_expired_approval_never_claims(self):
        with patch.object(tools, "get_approval", return_value={**self.row, "created_at": "2000-01-01T00:00:00Z"}), patch.object(tools, "execute_with_receipt") as claim, patch.object(tools, "record_event"):
            self.assertEqual(self.execute()["decision"], "DENY")
            claim.assert_not_called()

    def test_missing_approval_never_claims(self):
        with patch.object(tools, "get_approval", return_value=None), patch.object(tools, "execute_with_receipt") as claim, patch.object(tools, "record_event"):
            self.assertEqual(self.execute()["decision"], "DENY")
            claim.assert_not_called()

    def test_success_then_lost_claim(self):
        with patch.object(tools, "get_approval", return_value=self.row), patch.object(tools, "execute_with_receipt", side_effect=[{"decision": "ALLOW", "receipt_id": "test-receipt"}, {"decision": "DENY"}]) as claim, patch.object(tools, "record_event"):
            self.assertEqual(self.execute()["decision"], "ALLOW")
            self.assertEqual(self.execute()["decision"], "DENY")
            self.assertEqual(claim.call_count, 2)

    def test_database_failure_does_not_report_success(self):
        with patch.object(tools, "get_approval", side_effect=RuntimeError("database unavailable")), patch.object(tools, "execute_with_receipt") as claim:
            with self.assertRaises(RuntimeError):
                self.execute()
            claim.assert_not_called()

    def test_submission_passes_minor_units_and_request_id(self):
        expected = {"decision": "APPROVAL_REQUIRED", "approval_id": "apr_test"}
        with patch.object(tools, "submit_refund_request", return_value=expected) as submit:
            result = json.loads(asyncio.run(self.registered["issue_refund"]("req_test", "acct_001", 75000, "USD", "test", self.ctx)))
            self.assertEqual(result, expected)
            submit.assert_called_once_with("finance-agent", "req_test", "acct_001", 75000, "USD", "test")

    def test_invalid_submission_never_reaches_database(self):
        for amount in [-1, 0, True, 1.5]:
            with self.subTest(amount=amount), patch.object(tools, "submit_refund_request") as submit:
                result = json.loads(asyncio.run(self.registered["issue_refund"]("req_test", "acct_001", amount, "USD", "test", self.ctx)))
                self.assertEqual(result["decision"], "DENY")
                submit.assert_not_called()

    def test_submission_database_failure_fails_closed(self):
        with patch.object(tools, "submit_refund_request", side_effect=RuntimeError("database unavailable")):
            with self.assertRaises(RuntimeError):
                asyncio.run(self.registered["issue_refund"]("req_test", "acct_001", 100, "USD", "test", self.ctx))

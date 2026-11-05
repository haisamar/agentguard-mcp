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
            with self.subTest(status=status), patch.object(tools, "get_approval", return_value={**self.row, "status": status}), patch.object(tools, "mark_executed") as claim, patch.object(tools, "record_event"):
                self.assertEqual(self.execute()["decision"], "DENY")
                claim.assert_not_called()

    def test_wrong_identity_and_action_never_claim(self):
        for change in [{"identity": "other-agent"}, {"action": "export_customer_data"}]:
            with self.subTest(change=change), patch.object(tools, "get_approval", return_value={**self.row, **change}), patch.object(tools, "mark_executed") as claim, patch.object(tools, "record_event"):
                self.assertEqual(self.execute()["decision"], "DENY")
                claim.assert_not_called()

    def test_expired_approval_never_claims(self):
        with patch.object(tools, "get_approval", return_value={**self.row, "created_at": "2000-01-01T00:00:00Z"}), patch.object(tools, "mark_executed") as claim, patch.object(tools, "record_event"):
            self.assertEqual(self.execute()["decision"], "DENY")
            claim.assert_not_called()

    def test_missing_approval_never_claims(self):
        with patch.object(tools, "get_approval", return_value=None), patch.object(tools, "mark_executed") as claim, patch.object(tools, "record_event"):
            self.assertEqual(self.execute()["decision"], "DENY")
            claim.assert_not_called()

    def test_success_then_lost_claim(self):
        with patch.object(tools, "get_approval", return_value=self.row), patch.object(tools, "mark_executed", side_effect=[self.row, None]) as claim, patch.object(tools, "record_event"):
            self.assertEqual(self.execute()["decision"], "ALLOW")
            self.assertEqual(self.execute()["decision"], "DENY")
            self.assertEqual(claim.call_count, 2)

    def test_database_failure_does_not_report_success(self):
        with patch.object(tools, "get_approval", side_effect=RuntimeError("database unavailable")), patch.object(tools, "mark_executed") as claim:
            with self.assertRaises(RuntimeError):
                self.execute()
            claim.assert_not_called()

    def test_high_risk_request_creates_pending_approval(self):
        with patch.object(tools, "create_approval", return_value={"id": "apr_test"}) as create, patch.object(tools, "record_event"):
            result = json.loads(asyncio.run(self.registered["issue_refund"]("acct_001", 750, "test", self.ctx)))
            self.assertEqual(result["decision"], "APPROVAL_REQUIRED")
            create.assert_called_once()

    def test_invalid_amount_does_not_create_approval(self):
        with patch.object(tools, "create_approval") as create, patch.object(tools, "record_event"):
            result = json.loads(asyncio.run(self.registered["issue_refund"]("acct_001", -1, "test", self.ctx)))
            self.assertEqual(result["decision"], "DENY")
            create.assert_not_called()

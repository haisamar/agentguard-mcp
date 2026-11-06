"""ASGI transport regression checks with a mocked token verifier and audit sink.

These exercise actual MCP registration/routing, not Auth0 signature validation or
live database transactions. No production configuration or records are used.
"""
import importlib
import json
import os
import unittest
from unittest.mock import AsyncMock, patch

from starlette.testclient import TestClient


class TransportTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        with patch.dict(os.environ, {
            "AUTH0_DOMAIN": "example.auth0.com",
            "AUTH0_AUDIENCE": "https://agentguard.test",
            "MCP_SERVER_URL": "https://agentguard.test",
            "SUPABASE_URL": "https://example.supabase.co",
            "SUPABASE_SECRET_KEY": "ci-placeholder-not-a-secret",
            "DEBUG": "false",
        }):
            cls.server = importlib.import_module("src.server")
        cls.client = TestClient(cls.server.app, base_url="https://agentguard.test")
        cls.client.__enter__()
        cls.addClassCleanup(cls.client.__exit__, None, None, None)

    def setUp(self):
        self.verifier = patch(
            "src.auth0.middleware.ApiClient.verify_access_token",
            new_callable=AsyncMock,
            return_value={"sub": "transport-test-agent", "azp": "test-client", "scope": "crm:read"},
        )
        self.verify = self.verifier.start()
        self.addCleanup(self.verifier.stop)
        audit_patch = patch("src.tools.record_event")
        self.audit = audit_patch.start()
        self.addCleanup(audit_patch.stop)

    def call(self, method, params=None, **headers):
        return self.client.post("/mcp", json={
            "jsonrpc": "2.0", "id": 1, "method": method, "params": params or {},
        }, headers={
            "Authorization": "Bearer synthetic-test-token",
            "Accept": "application/json, text/event-stream",
            "MCP-Protocol-Version": "2025-11-25",
            **headers,
        })

    def result(self, response):
        self.assertEqual(response.status_code, 200, response.text)
        if response.headers.get("content-type", "").startswith("application/json"):
            return response.json()
        return json.loads(next(line[6:] for line in response.text.splitlines() if line.startswith("data: ")))

    def test_public_liveness_and_resource_metadata(self):
        self.assertEqual(self.client.get("/health").json()["status"], "ok")
        metadata = self.client.get("/.well-known/oauth-protected-resource")
        self.assertEqual(metadata.status_code, 200)
        self.assertEqual(metadata.json()["resource"], "https://agentguard.test")
        self.verify.assert_not_awaited()

    def test_missing_authentication_never_dispatches(self):
        response = self.client.post("/mcp", json={"jsonrpc": "2.0", "id": 1, "method": "tools/list"})
        self.assertIn(response.status_code, (400, 401))
        self.verify.assert_not_awaited()
        self.audit.assert_not_called()

    def test_registered_tools_and_authenticated_context(self):
        listing = self.result(self.call("tools/list"))
        self.assertIn("search_accounts", [tool["name"] for tool in listing["result"]["tools"]])
        result = self.result(self.call("tools/call", {"name": "search_accounts", "arguments": {"query": "Acme"}}))
        self.assertFalse(result["result"].get("isError", False), result)
        self.assertIn("acct_001", json.dumps(result))
        self.assertEqual(self.audit.call_args.kwargs["identity"], "transport-test-agent")

    def test_current_protocol_tool_call(self):
        result = self.result(self.call("tools/call", {
            "name": "search_accounts", "arguments": {"query": "Acme"},
            "_meta": {
                "io.modelcontextprotocol/protocolVersion": "2026-07-28",
                "io.modelcontextprotocol/clientCapabilities": {},
                "io.modelcontextprotocol/clientInfo": {"name": "agentguard-tests", "version": "1.0.0"},
            },
        }, **{
            "MCP-Protocol-Version": "2026-07-28",
            "Mcp-Method": "tools/call",
            "Mcp-Name": "search_accounts",
        }))
        self.assertNotIn("error", result, result)
        self.assertIn("acct_001", json.dumps(result))
        self.assertEqual(self.audit.call_args.kwargs["identity"], "transport-test-agent")

    def test_host_and_origin_allowlists_reject_other_sites(self):
        self.assertEqual(self.call("tools/list", Host="untrusted.test").status_code, 421)
        self.assertEqual(self.call("tools/list", Origin="https://untrusted.test").status_code, 403)

    def test_machine_approval_still_denied_over_transport(self):
        self.verify.return_value = {"sub": "transport-test-agent", "azp": "test-client", "scope": "agent:manage"}
        response = self.result(self.call("tools/call", {"name": "approve_action", "arguments": {"approval_id": "apr_test"}}))
        self.assertIn('"DENY"', json.dumps(response).replace('\\"', '"'))
        self.assertEqual(self.audit.call_args.kwargs["decision"], "DENY")

    def test_refund_contract_rejects_coerced_amounts(self):
        self.verify.return_value = {"sub": "transport-test-agent", "azp": "test-client", "scope": "finance:refund"}
        with patch("src.tools.submit_refund_request") as submit:
            for amount in [True, 1.5, "100"]:
                with self.subTest(amount=amount):
                    response = self.result(self.call("tools/call", {
                        "name": "issue_refund", "arguments": {
                            "request_id": "req_transport", "account_id": "acct_001",
                            "amount_minor": amount, "currency": "USD", "reason": "test",
                        },
                    }))
                    self.assertTrue(response["result"].get("isError"), response)
            submit.assert_not_called()

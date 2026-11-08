"""MCP transport checks, including locally signed JWTs and fixture discovery."""
import importlib
import json
import os
import time
import unittest
from unittest.mock import AsyncMock, patch

import jwt
from cryptography.hazmat.primitives.asymmetric import rsa
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
        now = int(time.time())
        self.verifier = patch(
            "src.auth0.middleware.ApiClient.verify_access_token",
            new_callable=AsyncMock,
            return_value={"sub": "transport-test-agent", "azp": "test-client", "scope": "crm:read", "iat": now, "exp": now + 600},
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
        self.verify.return_value["scope"] = "agent:manage"
        response = self.result(self.call("tools/call", {"name": "approve_action", "arguments": {"approval_id": "apr_test"}}))
        self.assertIn('"DENY"', json.dumps(response).replace('\\"', '"'))
        self.assertEqual(self.audit.call_args.kwargs["decision"], "DENY")

    def test_refund_contract_rejects_coerced_amounts(self):
        self.verify.return_value["scope"] = "finance:refund"
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

    def test_signed_tokens_use_real_sdk_verification_before_tool_dispatch(self):
        self.verifier.stop()
        key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        issuer = "https://example.auth0.com/"
        jwk = jwt.algorithms.RSAAlgorithm.to_jwk(key.public_key(), as_dict=True)
        jwk["kid"] = "agentguard-fixture"
        now = int(time.time())
        claims = {"iss": issuer, "aud": "https://agentguard.test", "iat": now,
                  "exp": now + 600, "sub": "signed-test-agent", "azp": "test-client", "scope": "crm:read"}

        def signed(changes=None, signing_key=key, kid=jwk["kid"]):
            return jwt.encode({**claims, **(changes or {})}, signing_key, algorithm="RS256", headers={"kid": kid})

        def call(token):
            return self.call("tools/call", {"name": "search_accounts", "arguments": {"query": "Acme"}}, Authorization="Bearer " + token)

        # Only external discovery and JWKS responses are replaced. The SDK
        # still performs signature verification and checks signed claims.
        with patch("auth0_api_python.api_client.fetch_oidc_metadata", new_callable=AsyncMock,
                   return_value=({"issuer": issuer, "jwks_uri": issuer + ".well-known/jwks.json"}, 60)) as discover, \
             patch("auth0_api_python.api_client.fetch_jwks", new_callable=AsyncMock) as keys:
            keys.side_effect = RuntimeError("Fixture JWKS unavailable")
            self.assertEqual(call(signed()).status_code, 401)
            self.audit.assert_not_called()
            keys.side_effect = None
            keys.return_value = ({"keys": [jwk]}, 60)
            valid = self.result(call(signed()))
            self.assertIn("acct_001", json.dumps(valid))
            self.assertEqual(self.audit.call_args.kwargs["identity"], "signed-test-agent")
            self.audit.reset_mock()
            discover.assert_awaited()
            keys.assert_awaited()

            for case, token in {
                "wrong issuer": signed({"iss": "https://foreign.example/"}),
                "wrong audience": signed({"aud": ["https://foreign.example"]}),
                "expired": signed({"iat": now - 600, "exp": now - 60}),
                "wrong signing key": signed(signing_key=other_key),
                "unknown key id": signed(kid="unknown"),
                "future activation": signed({"nbf": now + 90}),
                "future issue time": signed({"iat": now + 90}),
                "malformed expiry": signed({"exp": str(now + 600)}),
                "malformed scope": signed({"scope": ["crm:read"]}),
                "empty subject": signed({"sub": " "}),
            }.items():
                with self.subTest(case=case):
                    response = call(token)
                    self.assertEqual(response.status_code, 401, response.text)
                    self.assertIn("Bearer", response.headers["www-authenticate"])
                    self.audit.assert_not_called()

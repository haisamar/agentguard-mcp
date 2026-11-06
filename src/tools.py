import json
import re

from mcp.server.mcpserver import Context
from pydantic import StrictInt

from .auth0 import Auth0Mcp
from .auth0.authz import register_required_scopes, require_scopes
from .audit import record_event
from .approvals import (
    approval_expired,
    submit_refund_request,
    get_approval,
    list_pending_approvals,
    execute_with_receipt,
)


ACCOUNTS = [
    {
        "id": "acct_001",
        "company_name": "Acme Corp",
        "owner": "Sarah Chen",
        "stage": "Discovery",
        "annual_value": 48000,
    },
    {
        "id": "acct_002",
        "company_name": "Northstar Technologies",
        "owner": "Marcus Lee",
        "stage": "Qualified",
        "annual_value": 72000,
    },
    {
        "id": "acct_003",
        "company_name": "Vertex Labs",
        "owner": "Emily Parker",
        "stage": "Proposal",
        "annual_value": 36000,
    },
]


def register_tools(auth0_mcp: Auth0Mcp) -> None:
    mcp = auth0_mcp.mcp

    # ---------------------------------------------------------
    # CRM
    # ---------------------------------------------------------

    @mcp.tool(
        name="search_accounts",
        title="Search CRM Accounts",
        description="Search CRM accounts by company name.",
        annotations={
            "read_only_hint": True,
            "destructive_hint": False,
            "idempotent_hint": True,
            "open_world_hint": False,
        },
    )
    @require_scopes(["crm:read"])
    async def search_accounts(query: str, ctx: Context) -> str:
        query = query.strip().lower()

        results = [
            account
            for account in ACCOUNTS
            if query in account["company_name"].lower()
        ]

        auth_info = ctx.request_context.request.state.auth
        identity = auth_info.get("extra", {}).get("sub")

        record_event(
            identity=identity,
            action="search_accounts",
            decision="ALLOW",
            required_scope="crm:read",
            reason="Identity is authorized to read CRM accounts.",
            metadata={
                "query": query,
                "result_count": len(results),
            },
        )

        return json.dumps(
            {
                "identity": identity,
                "required_permission": "crm:read",
                "decision": "ALLOW",
                "results": results,
            },
            indent=2,
        )

    # ---------------------------------------------------------
    # FINANCE
    # ---------------------------------------------------------

    @mcp.tool(
        name="issue_refund",
        title="Issue Customer Refund",
        description="Submit a simulated USD refund. Use integer cents and a stable request_id; retries return the original submission result. Legacy amount calls must migrate to contract v2.",
        annotations={
            "read_only_hint": False,
            "destructive_hint": True,
            "idempotent_hint": False,
            "open_world_hint": False,
        },
    )
    @require_scopes(["finance:refund"])
    async def issue_refund(
        request_id: str,
        account_id: str,
        amount_minor: StrictInt,
        currency: str,
        reason: str,
        ctx: Context,
    ) -> str:
        identity = ctx.request_context.request.state.auth.get("extra", {}).get("sub")
        if (not identity or type(amount_minor) is not int or amount_minor <= 0
                or amount_minor > 99999999999900 or currency != "USD"
                or account_id not in {a["id"] for a in ACCOUNTS}
                or not isinstance(request_id, str)
                or not re.fullmatch(r"[a-zA-Z0-9_-]{1,128}", request_id)
                or not isinstance(reason, str) or not reason.strip() or len(reason) > 2000):
            return json.dumps({"decision": "DENY", "reason": "Invalid v2 refund request."})
        result = submit_refund_request(identity, request_id, account_id, amount_minor, currency, reason)
        return json.dumps(result, indent=2)

    # ---------------------------------------------------------
    # APPROVAL MANAGEMENT
    # ---------------------------------------------------------

    @mcp.tool(
        name="list_pending_approvals",
        title="List Pending Approvals",
        description="List AgentGuard actions waiting for human approval.",
        annotations={
            "read_only_hint": True,
            "destructive_hint": False,
            "idempotent_hint": True,
            "open_world_hint": False,
        },
    )
    @require_scopes(["agent:manage"])
    async def pending_approvals(ctx: Context) -> str:
        auth_info = ctx.request_context.request.state.auth
        identity = auth_info.get("extra", {}).get("sub")

        approvals = list_pending_approvals()

        record_event(
            identity=identity,
            action="list_pending_approvals",
            decision="ALLOW",
            required_scope="agent:manage",
            reason="Admin identity viewed pending approvals.",
            metadata={
                "count": len(approvals),
            },
        )

        return json.dumps(
            {
                "count": len(approvals),
                "approvals": approvals,
            },
            indent=2,
        )

    @mcp.tool(
        name="approve_action",
        title="Approve Pending Action",
        description="Approve an AgentGuard action waiting for human review.",
        annotations={
            "read_only_hint": False,
            "destructive_hint": True,
            "idempotent_hint": False,
            "open_world_hint": False,
        },
    )
    @require_scopes(["agent:manage"])
    async def approve_action(
        approval_id: str,
        ctx: Context,
    ) -> str:
        auth_info = ctx.request_context.request.state.auth
        approver = auth_info.get("extra", {}).get("sub")

        # Human approvals are issued only by the authenticated dashboard,
        # which enforces the administrator email allowlist. A machine token
        # with agent:manage must not cross that human authority boundary.
        record_event(
            identity=approver or "unknown",
            action="approve_action",
            decision="DENY",
            required_scope="agent:manage",
            reason="Human approval must be completed in the administrator dashboard.",
            metadata={"security_event": "approval_bypass_attempt"},
        )
        return json.dumps({
            "decision": "DENY",
            "reason": "Use the authenticated administrator dashboard to review this action.",
        })

    # ---------------------------------------------------------
    # APPROVED EXECUTION
    # ---------------------------------------------------------

    @mcp.tool(
        name="execute_approved_refund",
        title="Execute Approved Refund",
        description="Execute a refund after human approval.",
        annotations={
            "read_only_hint": False,
            "destructive_hint": True,
            "idempotent_hint": False,
            "open_world_hint": False,
        },
    )
    @require_scopes(["finance:refund"])
    async def execute_approved_refund(
        approval_id: str,
        ctx: Context,
    ) -> str:
        auth_info = ctx.request_context.request.state.auth
        identity = auth_info.get("extra", {}).get("sub")

        approval = get_approval(approval_id)

        if not approval:
            record_event(
                identity=identity,
                action="execute_approved_refund",
                decision="DENY",
                required_scope="finance:refund",
                reason="Approval request not found.",
                metadata={
                    "requested_approval_id": approval_id,
                },
            )

            return json.dumps(
                {
                    "decision": "DENY",
                    "reason": "Approval request not found.",
                },
                indent=2,
            )

        # Replay protection
        if approval["status"] == "EXECUTED":
            record_event(
                identity=identity,
                action="execute_approved_refund",
                decision="DENY",
                required_scope="finance:refund",
                reason="Approved action has already been executed.",
                approval_id=approval_id,
                metadata={
                    "security_event": "replay_attempt",
                },
            )

            return json.dumps(
                {
                    "decision": "DENY",
                    "reason": "Approved action has already been executed.",
                    "approval_id": approval_id,
                },
                indent=2,
            )

        if approval["status"] != "APPROVED":
            record_event(
                identity=identity,
                action="execute_approved_refund",
                decision="DENY",
                required_scope="finance:refund",
                reason="Action has not been approved.",
                approval_id=approval_id,
                metadata={
                    "approval_status": approval["status"],
                },
            )

            return json.dumps(
                {
                    "decision": "DENY",
                    "reason": "Action has not been approved.",
                    "approval_id": approval_id,
                    "status": approval["status"],
                },
                indent=2,
            )

        if approval["action"] != "issue_refund":
            record_event(
                identity=identity,
                action="execute_approved_refund",
                decision="DENY",
                required_scope="finance:refund",
                reason="Approval does not authorize a refund.",
                approval_id=approval_id,
                metadata={
                    "approved_action": approval["action"],
                },
            )

            return json.dumps(
                {
                    "decision": "DENY",
                    "reason": "Approval does not authorize a refund.",
                },
                indent=2,
            )

        # Approval can only be used by the identity that requested it
        if approval["identity"] != identity:
            record_event(
                identity=identity,
                action="execute_approved_refund",
                decision="DENY",
                required_scope="finance:refund",
                reason="Approval belongs to a different agent identity.",
                approval_id=approval_id,
                metadata={
                    "requesting_identity": approval["identity"],
                    "attempting_identity": identity,
                },
            )

            return json.dumps(
                {
                    "decision": "DENY",
                    "reason": "Approval belongs to a different agent identity.",
                },
                indent=2,
            )

        if approval_expired(approval):
            record_event(
                identity=identity, action="execute_approved_refund", decision="DENY",
                required_scope="finance:refund", approval_id=approval_id,
                reason="Approval has expired or has an invalid creation time.",
                metadata={"security_event": "expired_approval"},
            )
            return json.dumps({"decision": "DENY", "reason": "Approval has expired.", "approval_id": approval_id})

        result = execute_with_receipt(approval_id, identity)
        if result["decision"] == "DENY":
            record_event(
                identity=identity, action="execute_approved_refund", decision="DENY",
                required_scope="finance:refund", approval_id=approval_id,
                reason=result.get("reason", "Receipt transaction denied execution."),
                metadata={"security_event": "execution_transaction_denied"},
            )
        return json.dumps(result, indent=2)

    register_required_scopes(auth0_mcp)

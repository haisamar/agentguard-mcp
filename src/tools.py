import json

from mcp.server.fastmcp import Context

from .auth0 import Auth0Mcp
from .auth0.authz import register_required_scopes, require_scopes
from .policy import Decision, evaluate
from .audit import record_event
from .approvals import (
    approve_approval,
    create_approval,
    get_approval,
    list_pending_approvals,
    mark_executed,
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
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
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
        description="Issue a refund to a customer account.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    @require_scopes(["finance:refund"])
    async def issue_refund(
        account_id: str,
        amount: float,
        reason: str,
        ctx: Context,
    ) -> str:
        auth_info = ctx.request_context.request.state.auth
        identity = auth_info.get("extra", {}).get("sub")

        policy = evaluate(
            action="issue_refund",
            context={
                "account_id": account_id,
                "amount": amount,
                "reason": reason,
            },
        )

        # Sensitive refund -> create approval request
        if policy["decision"] == Decision.APPROVAL_REQUIRED:
            approval = create_approval(
                identity=identity,
                action="issue_refund",
                payload={
                    "account_id": account_id,
                    "amount": amount,
                    "reason": reason,
                },
                reason=policy["reason"],
            )

            record_event(
                identity=identity,
                action="issue_refund",
                decision="APPROVAL_REQUIRED",
                required_scope="finance:refund",
                reason=policy["reason"],
                approval_id=approval["id"],
                metadata={
                    "account_id": account_id,
                    "amount": amount,
                    "reason": reason,
                },
            )

            return json.dumps(
                {
                    "identity": identity,
                    "required_permission": "finance:refund",
                    "decision": "APPROVAL_REQUIRED",
                    "reason": policy["reason"],
                    "approval_id": approval["id"],
                    "account_id": account_id,
                    "amount": amount,
                    "status": "pending_human_approval",
                },
                indent=2,
            )

        # Contextual policy explicitly denied the action
        if policy["decision"] == Decision.DENY:
            record_event(
                identity=identity,
                action="issue_refund",
                decision="DENY",
                required_scope="finance:refund",
                reason=policy["reason"],
                metadata={
                    "account_id": account_id,
                    "amount": amount,
                    "reason": reason,
                },
            )

            return json.dumps(
                {
                    "identity": identity,
                    "required_permission": "finance:refund",
                    "decision": "DENY",
                    "reason": policy["reason"],
                    "account_id": account_id,
                    "amount": amount,
                    "status": "blocked",
                },
                indent=2,
            )

        # Normal refund allowed
        record_event(
            identity=identity,
            action="issue_refund",
            decision="ALLOW",
            required_scope="finance:refund",
            reason="Refund satisfied AgentGuard contextual policy.",
            metadata={
                "account_id": account_id,
                "amount": amount,
                "reason": reason,
            },
        )

        return json.dumps(
            {
                "identity": identity,
                "required_permission": "finance:refund",
                "decision": "ALLOW",
                "account_id": account_id,
                "amount": amount,
                "reason": reason,
                "status": "refund_processed",
            },
            indent=2,
        )

    # ---------------------------------------------------------
    # APPROVAL MANAGEMENT
    # ---------------------------------------------------------

    @mcp.tool(
        name="list_pending_approvals",
        title="List Pending Approvals",
        description="List AgentGuard actions waiting for human approval.",
        annotations={
            "readOnlyHint": True,
            "destructiveHint": False,
            "idempotentHint": True,
            "openWorldHint": False,
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
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
        },
    )
    @require_scopes(["agent:manage"])
    async def approve_action(
        approval_id: str,
        ctx: Context,
    ) -> str:
        auth_info = ctx.request_context.request.state.auth
        approver = auth_info.get("extra", {}).get("sub")

        approval = approve_approval(
            approval_id=approval_id,
            approved_by=approver,
        )

        if not approval:
            record_event(
                identity=approver,
                action="approve_action",
                decision="DENY",
                required_scope="agent:manage",
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

        record_event(
            identity=approver,
            action="approve_action",
            decision="APPROVED",
            required_scope="agent:manage",
            approval_id=approval["id"],
            reason="Human administrator approved the requested action.",
            metadata={
                "requesting_identity": approval["identity"],
                "original_action": approval["action"],
            },
        )

        return json.dumps(
            {
                "decision": "APPROVED",
                "approval_id": approval["id"],
                "approved_by": approval["approved_by"],
                "approval": approval,
            },
            indent=2,
        )

    # ---------------------------------------------------------
    # APPROVED EXECUTION
    # ---------------------------------------------------------

    @mcp.tool(
        name="execute_approved_refund",
        title="Execute Approved Refund",
        description="Execute a refund after human approval.",
        annotations={
            "readOnlyHint": False,
            "destructiveHint": True,
            "idempotentHint": False,
            "openWorldHint": False,
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

        payload = approval["payload"]

        mark_executed(approval_id)

        record_event(
            identity=identity,
            action="execute_approved_refund",
            decision="ALLOW",
            required_scope="finance:refund",
            reason="Human approval verified.",
            approval_id=approval_id,
            metadata={
                "account_id": payload["account_id"],
                "amount": payload["amount"],
                "approved_by": approval["approved_by"],
            },
        )

        return json.dumps(
            {
                "identity": identity,
                "approval_id": approval_id,
                "approved_by": approval["approved_by"],
                "decision": "ALLOW",
                "account_id": payload["account_id"],
                "amount": payload["amount"],
                "reason": payload["reason"],
                "status": "refund_processed",
            },
            indent=2,
        )

    register_required_scopes(auth0_mcp)
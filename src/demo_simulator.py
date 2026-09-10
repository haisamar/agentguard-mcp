from .audit import record_event
from .policy import Decision, evaluate
from .approvals import (
    create_approval,
    approve_approval,
    mark_executed,
)


SALES_AGENT = "sales-agent-demo"
FINANCE_AGENT = "finance-agent-demo"
ADMIN = "admin-human-demo"


AGENT_SCOPES = {
    SALES_AGENT: [
        "crm:read",
        "crm:write",
        "support:read",
    ],
    FINANCE_AGENT: [
        "crm:read",
        "finance:read",
        "finance:refund",
    ],
    ADMIN: [
        "agent:manage",
    ],
}


REFUND_SCOPE = "finance:refund"


def simulate_refund(
    identity: str,
    amount: float,
    reason: str,
):
    granted_scopes = AGENT_SCOPES.get(
        identity,
        [],
    )


    # ---------------------------------------------------------
    # STEP 1 — AUTHORIZATION
    # ---------------------------------------------------------

    if REFUND_SCOPE not in granted_scopes:

        record_event(
            identity=identity,
            action="issue_refund",
            decision="DENY",
            required_scope=REFUND_SCOPE,
            reason="Missing required OAuth scope: finance:refund",
            metadata={
                "amount": amount,
                "account_id": "acct_demo_001",
                "security_event": "authorization_failure",
                "missing_scopes": [
                    REFUND_SCOPE,
                ],
                "granted_scopes": granted_scopes,
                "demo": True,
            },
        )

        return None


    # ---------------------------------------------------------
    # STEP 2 — CONTEXTUAL POLICY
    # ---------------------------------------------------------

    policy = evaluate(
        action="issue_refund",
        context={
            "account_id": "acct_demo_001",
            "amount": amount,
            "reason": reason,
        },
    )


    # ---------------------------------------------------------
    # STEP 3 — HUMAN APPROVAL REQUIRED
    # ---------------------------------------------------------

    if policy["decision"] == Decision.APPROVAL_REQUIRED:

        approval = create_approval(
            identity=identity,
            action="issue_refund",
            payload={
                "account_id": "acct_demo_001",
                "amount": amount,
                "reason": reason,
            },
            reason=policy["reason"],
        )


        record_event(
            identity=identity,
            action="issue_refund",
            decision="APPROVAL_REQUIRED",
            required_scope=REFUND_SCOPE,
            reason=policy["reason"],
            approval_id=approval["id"],
            metadata={
                "amount": amount,
                "account_id": "acct_demo_001",
                "granted_scopes": granted_scopes,
                "policy_result": "high_risk_action",
                "human_review_required": True,
                "demo": True,
            },
        )


        return approval


    # ---------------------------------------------------------
    # STEP 4 — POLICY DENY
    # ---------------------------------------------------------

    if policy["decision"] == Decision.DENY:

        record_event(
            identity=identity,
            action="issue_refund",
            decision="DENY",
            required_scope=REFUND_SCOPE,
            reason=policy["reason"],
            metadata={
                "amount": amount,
                "account_id": "acct_demo_001",
                "granted_scopes": granted_scopes,
                "policy_result": "denied",
                "demo": True,
            },
        )


        return None


    # ---------------------------------------------------------
    # STEP 5 — AUTONOMOUS ALLOW
    # ---------------------------------------------------------

    record_event(
        identity=identity,
        action="issue_refund",
        decision="ALLOW",
        required_scope=REFUND_SCOPE,
        reason=policy["reason"],
        metadata={
            "amount": amount,
            "account_id": "acct_demo_001",
            "granted_scopes": granted_scopes,
            "policy_result": "allowed",
            "human_review_required": False,
            "demo": True,
        },
    )


    return None




def run_demo():

    print("\nStarting AgentGuard security demo...\n")


    # ---------------------------------------------------------
    # SCENARIO 1
    # SALES AGENT → SCOPE DENIED
    # ---------------------------------------------------------

    print(
        "1. Sales Agent attempts $750 refund"
    )

    print(
        "   Expected: DENY — missing finance:refund\n"
    )


    simulate_refund(
        SALES_AGENT,
        750,
        "Customer refund request",
    )



    # ---------------------------------------------------------
    # SCENARIO 2
    # FINANCE AGENT → AUTONOMOUS ALLOW
    # ---------------------------------------------------------

    print(
        "2. Finance Agent requests $100 refund"
    )

    print(
        "   Expected: ALLOW — permission and policy satisfied\n"
    )


    simulate_refund(
        FINANCE_AGENT,
        100,
        "Small customer refund",
    )



    # ---------------------------------------------------------
    # SCENARIO 3
    # FINANCE AGENT → APPROVAL REQUIRED
    # ---------------------------------------------------------

    print(
        "3. Finance Agent requests $750 refund"
    )

    print(
        "   Expected: APPROVAL_REQUIRED — exceeds autonomous limit\n"
    )


    approval = simulate_refund(
        FINANCE_AGENT,
        750,
        "Large customer refund",
    )



    # ---------------------------------------------------------
    # SCENARIO 4
    # HUMAN APPROVAL + EXECUTION
    # ---------------------------------------------------------

    if approval:

        print(
            "4. Human Administrator approves request"
        )


        approve_approval(
            approval["id"],
            ADMIN,
        )


        record_event(
            identity=ADMIN,
            action="approve_action",
            decision="ALLOW",
            required_scope="agent:manage",
            reason="Authenticated human approved sensitive agent action.",
            approval_id=approval["id"],
            metadata={
                "requesting_identity": FINANCE_AGENT,
                "amount": 750,
                "account_id": "acct_demo_001",
                "demo": True,
            },
        )


        print(
            "   Expected: APPROVED\n"
        )



        print(
            "5. Finance Agent executes approved refund"
        )


        mark_executed(
            approval["id"]
        )


        record_event(
            identity=FINANCE_AGENT,
            action="execute_approved_refund",
            decision="ALLOW",
            required_scope=REFUND_SCOPE,
            approval_id=approval["id"],
            reason="Human approval verified. Approved refund executed.",
            metadata={
                "amount": 750,
                "account_id": "acct_demo_001",
                "human_approval_verified": True,
                "demo": True,
            },
        )


        print(
            "   Expected: EXECUTED\n"
        )



    # ---------------------------------------------------------
    # SCENARIO 5
    # LEAVE ONE APPROVAL PENDING
    # ---------------------------------------------------------

    print(
        "6. Finance Agent requests $900 refund"
    )


    print(
        "   Expected: APPROVAL_REQUIRED — left pending for dashboard review\n"
    )


    simulate_refund(
        FINANCE_AGENT,
        900,
        "High-value refund awaiting administrator review",
    )



    print(
        "AgentGuard demo completed."
    )


    print(
        "\nExpected dashboard state:"
    )

    print(
        "- Sales Agent scope denial"
    )

    print(
        "- Finance Agent autonomous allow"
    )

    print(
        "- Finance Agent human-approved execution"
    )

    print(
        "- Human Administrator approval event"
    )

    print(
        "- One pending approval"
    )



if __name__ == "__main__":
    run_demo()
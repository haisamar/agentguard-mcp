from enum import Enum


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


def evaluate(action: str, context: dict) -> dict:
    if action == "issue_refund":
        amount = float(context.get("amount", 0))

        if amount > 500:
            return {
                "decision": Decision.APPROVAL_REQUIRED,
                "reason": "Refunds above $500 require human approval.",
            }

    if action == "export_customer_data":
        return {
            "decision": Decision.APPROVAL_REQUIRED,
            "reason": "Customer data exports require human approval.",
        }

    if action == "delete_customer":
        return {
            "decision": Decision.DENY,
            "reason": "Customer deletion is human-only.",
        }

    return {
        "decision": Decision.ALLOW,
        "reason": "Contextual policy satisfied.",
    }
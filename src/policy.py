from enum import Enum
import math


class Decision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    APPROVAL_REQUIRED = "APPROVAL_REQUIRED"


def evaluate(action: str, context: dict) -> dict:
    if action == "issue_refund":
        try:
            raw_amount = context.get("amount")
            amount = float(raw_amount)
        except (TypeError, ValueError, OverflowError):
            amount = float("nan")
        if isinstance(raw_amount, bool) or not math.isfinite(amount) or amount <= 0:
            return {
                "decision": Decision.DENY,
                "reason": "Refund amount must be a positive finite number.",
            }

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
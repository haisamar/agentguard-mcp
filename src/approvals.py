from datetime import datetime, timezone, timedelta
from uuid import uuid4

from .database import supabase

# Approval validity is measured from request creation, not review time.
APPROVAL_TTL_SECONDS = 3600


def approval_cutoff() -> str:
    return (datetime.now(timezone.utc) - timedelta(seconds=APPROVAL_TTL_SECONDS)).isoformat()


def approval_expired(approval: dict) -> bool:
    try:
        created = datetime.fromisoformat(approval["created_at"].replace("Z", "+00:00"))
        if created.tzinfo is None:
            return True
        return created <= datetime.now(timezone.utc) - timedelta(seconds=APPROVAL_TTL_SECONDS)
    except (KeyError, TypeError, ValueError, AttributeError):
        return True



def _normalize(row: dict | None) -> dict | None:
    if not row:
        return None

    # Keep the rest of AgentGuard compatible with our existing code.
    return {
        "id": row["id"],
        "identity": row["requesting_identity"],
        "action": row["action"],
        "payload": row["payload"],
        "reason": row["reason"],
        "status": row["status"],
        "created_at": row["created_at"],
        "approved_at": row["approved_at"],
        "approved_by": row["approved_by"],
        "executed_at": row["executed_at"],
    }


def create_approval(
    identity: str,
    action: str,
    payload: dict,
    reason: str,
) -> dict:
    approval_id = f"apr_{uuid4().hex[:10]}"

    response = (
        supabase.table("approvals")
        .insert(
            {
                "id": approval_id,
                "requesting_identity": identity,
                "action": action,
                "payload": payload,
                "reason": reason,
                "status": "PENDING",
            }
        )
        .execute()
    )

    return _normalize(response.data[0])


def get_approval(approval_id: str) -> dict | None:
    response = (
        supabase.table("approvals")
        .select("*")
        .eq("id", approval_id)
        .limit(1)
        .execute()
    )

    if not response.data:
        return None

    return _normalize(response.data[0])


def list_pending_approvals() -> list[dict]:
    response = (
        supabase.table("approvals")
        .select("*")
        .eq("status", "PENDING")
        .order("created_at", desc=True)
        .execute()
    )

    return [_normalize(row) for row in response.data]


def approve_approval(
    approval_id: str,
    approved_by: str,
) -> dict | None:
    approval = get_approval(approval_id)

    if not approval:
        return None

    if approval_expired(approval):
        return None

    if approval["status"] != "PENDING":
        return None

    approved_at = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("approvals")
        .update(
            {
                "status": "APPROVED",
                "approved_by": approved_by,
                "approved_at": approved_at,
            }
        )
        .eq("id", approval_id)
        .eq("status", "PENDING")
        .gt("created_at", approval_cutoff())
        .execute()
    )

    if not response.data:
        return None

    return _normalize(response.data[0])


def mark_executed(approval_id: str) -> dict | None:
    executed_at = datetime.now(timezone.utc).isoformat()

    response = (
        supabase.table("approvals")
        .update(
            {
                "status": "EXECUTED",
                "executed_at": executed_at,
            }
        )
        .eq("id", approval_id)
        .eq("status", "APPROVED")
        .gt("created_at", approval_cutoff())
        .execute()
    )

    if not response.data:
        return None

    return _normalize(response.data[0])

def execute_with_receipt(approval_id: str, identity: str) -> dict:
    """Database transaction owns validation, ledger effect, state and audit write."""
    response = supabase.rpc("execute_refund_with_receipt", {
        "p_approval_id": approval_id, "p_identity": identity,
    }).execute()
    if not isinstance(response.data, dict) or response.data.get("decision") not in ("ALLOW", "DENY"):
        raise RuntimeError("Invalid receipt transaction response")
    return response.data


def record_autonomous_refund(identity: str, account_id: str, amount: float) -> dict:
    result = supabase.rpc("record_autonomous_refund", {
        "p_identity": identity, "p_account_id": account_id, "p_amount": amount,
    }).execute().data
    if not isinstance(result, dict) or result.get("decision") not in ("ALLOW", "DENY", "APPROVAL_REQUIRED"):
        raise RuntimeError("Invalid autonomous refund transaction response")
    return result

from datetime import datetime, timezone
from uuid import uuid4

from .database import supabase


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

    if approval["status"] != "PENDING":
        return approval

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
        .execute()
    )

    if not response.data:
        return get_approval(approval_id)

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
        .execute()
    )

    if not response.data:
        return get_approval(approval_id)

    return _normalize(response.data[0])
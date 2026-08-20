from .database import supabase


def record_event(
    identity: str,
    action: str,
    decision: str,
    required_scope: str | None = None,
    reason: str | None = None,
    approval_id: str | None = None,
    metadata: dict | None = None,
) -> dict:
    event = {
        "identity": identity,
        "action": action,
        "decision": decision,
        "required_scope": required_scope,
        "reason": reason,
        "approval_id": approval_id,
        "metadata": metadata or {},
    }

    response = (
        supabase.table("audit_events")
        .insert(event)
        .execute()
    )

    return response.data[0]


def list_recent_events(limit: int = 20) -> list[dict]:
    response = (
        supabase.table("audit_events")
        .select("*")
        .order("created_at", desc=True)
        .limit(limit)
        .execute()
    )

    return response.data
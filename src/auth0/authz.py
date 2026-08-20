from __future__ import annotations

import logging
from collections.abc import Iterable
from functools import wraps

from mcp.server.fastmcp import Context

from . import Auth0Mcp
from .errors import AuthenticationRequired, InsufficientScope
from ..audit import record_event


logger = logging.getLogger(__name__)

# Collect required scopes from all decorated functions
_scopes_required: set[str] = set()


def _record_authorization_event(
    *,
    identity: str,
    action: str,
    decision: str,
    required_scopes: list[str],
    reason: str,
    metadata: dict | None = None,
) -> None:
    """
    Write authorization decisions to AgentGuard's audit trail.

    Audit failures must never change the authorization result itself.
    """
    try:
        record_event(
            identity=identity,
            action=action,
            decision=decision,
            required_scope=", ".join(required_scopes),
            reason=reason,
            metadata=metadata or {},
        )
    except Exception:
        logger.exception("Failed to write authorization audit event")


def require_scopes(required_scopes: Iterable[str]):
    """
    Decorator that requires scopes on MCP tools.

    Example:
      @mcp.tool(...)
      @require_scopes(["tool:greet", "tool:whoami"])
      async def my_tool(name: str, ctx: Context) -> str:
        return f"Hello {name}!"
    """
    required_scopes_list = list(required_scopes)

    # Collect scopes when decorator is applied
    _scopes_required.update(required_scopes_list)

    def decorator(func):
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # ctx is passed either by keyword or position
            ctx: Context | None = (
                kwargs.get("ctx")
                if isinstance(kwargs.get("ctx"), Context)
                else None
            ) or next(
                (
                    arg
                    for arg in args
                    if isinstance(arg, Context)
                ),
                None,
            )

            if ctx is None:
                raise TypeError("ctx: Context is required")

            auth = getattr(
                ctx.request_context.request.state,
                "auth",
                {},
            )

            action = func.__name__

            # -------------------------------------------------
            # Authentication failure
            # -------------------------------------------------

            if not auth:
                _record_authorization_event(
                    identity="anonymous",
                    action=action,
                    decision="DENY",
                    required_scopes=required_scopes_list,
                    reason="Authentication required.",
                    metadata={
                        "security_event": "authentication_failure",
                    },
                )

                raise AuthenticationRequired(
                    "Authentication required"
                )

            identity = (
                auth.get("extra", {}).get("sub")
                or auth.get("sub")
                or "unknown"
            )

            user_scopes = set(auth.get("scopes", []))

            missing_scopes = [
                scope
                for scope in required_scopes_list
                if scope not in user_scopes
            ]

            # -------------------------------------------------
            # Authorization failure
            # -------------------------------------------------

            if missing_scopes:
                reason = (
                    f"Missing required scopes: {missing_scopes}"
                )

                _record_authorization_event(
                    identity=identity,
                    action=action,
                    decision="DENY",
                    required_scopes=required_scopes_list,
                    reason=reason,
                    metadata={
                        "security_event": "authorization_failure",
                        "missing_scopes": missing_scopes,
                        "granted_scopes": sorted(user_scopes),
                    },
                )

                raise InsufficientScope(reason)

            return await func(*args, **kwargs)

        return wrapper

    return decorator


def register_required_scopes(
    auth0_mcp: Auth0Mcp,
) -> None:
    """
    Register all scopes collected from
    @require_scopes decorators.
    """
    if _scopes_required:
        auth0_mcp.register_scopes(
            list(_scopes_required)
        )

        _scopes_required.clear()
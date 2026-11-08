import logging
import time
from collections.abc import Callable
from typing import Any

from auth0_api_python import ApiClient, ApiClientOptions
from auth0_api_python.errors import VerifyAccessTokenError
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
from starlette.types import ASGIApp

from .errors import AuthenticationRequired, MalformedAuthorizationRequest

logger = logging.getLogger(__name__)

class Auth0Middleware(BaseHTTPMiddleware):
    """
    Middleware that requires a valid Bearer token in the Authorization header.
    Validates the token using Auth0 SDK Client and stores auth info in request.state.auth.
    """

    def __init__(self, app: ASGIApp, domain: str, audience: str):
        super().__init__(app)
        if not domain or not audience:
            raise RuntimeError("domain and audience must be provided")
        self.client = ApiClient(ApiClientOptions(
            domain=domain,
            audience=audience
        ))

    def _build_auth_data(self, token: dict[str, Any]) -> dict[str, Any]:
        """Extract authentication data from verified token."""
        client_id = token.get('client_id') or token.get('azp')
        subject = token.get('sub')
        if not isinstance(client_id, str) or not client_id.strip() or not isinstance(subject, str) or not subject.strip():
            raise VerifyAccessTokenError("Token has invalid identity claims")

        now = int(time.time())
        expiry, issued, not_before = token.get("exp"), token.get("iat"), token.get("nbf")
        if (type(expiry) is not int or expiry <= now or type(issued) is not int
                or issued > now + 30 or issued >= expiry
                or ("nbf" in token and (type(not_before) is not int or not_before > now))):
            raise VerifyAccessTokenError("Token has invalid time claims")
        scope = token.get("scope", "")
        if not isinstance(scope, str):
            raise VerifyAccessTokenError("Token has invalid scope claim")
        scopes = scope.split()

        auth_data = {
            "client_id": client_id,
            "scopes": scopes,
        }

        auth_data["expires_at"] = expiry

        # Extract extra claims with dict comprehension
        extra_fields = {'sub', 'azp', 'name', 'email', 'client_id'}
        auth_data["extra"] = {
            field: token[field]
            for field in extra_fields
            if field in token
        }

        return auth_data

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        # Extract Authorization header
        auth_header = request.headers.get("authorization")
        if not auth_header:
            raise MalformedAuthorizationRequest("Missing Authorization header")
        if not auth_header.lower().startswith("bearer "):
            raise MalformedAuthorizationRequest("Invalid Authorization header format")

        # Extract and verify token
        token = auth_header[7:].strip() # Remove "Bearer " prefix
        if not token:
            raise MalformedAuthorizationRequest("Missing bearer token")
        try:
            try:
                decoded_and_verified_token = await self.client.verify_access_token(token, required_claims=["sub"])
            except (TypeError, ValueError) as error:
                # The SDK may raise while comparing a malformed signed exp.
                raise VerifyAccessTokenError("Invalid token claim format") from error

            # Set up authentication context
            request.state.auth = self._build_auth_data(decoded_and_verified_token)

            return await call_next(request)
        except VerifyAccessTokenError:
            logger.info("Token verification failed")
            raise AuthenticationRequired("Invalid token")
        except Exception:
            logger.exception("Unexpected error in middleware")
            raise

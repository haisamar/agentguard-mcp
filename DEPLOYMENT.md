# AgentGuard MCP hosting

The frontend is hosted separately on Vercel. This repository is a long-running ASGI MCP service.

## Container

Build with `docker build -t agentguard-mcp .` and run with `docker run --rm --env-file .env -p 3001:3001 agentguard-mcp`.

The container runs as a non-root user, listens on 0.0.0.0, and respects PORT. Environment files are excluded from the build context.

Required runtime configuration: AUTH0_DOMAIN, AUTH0_AUDIENCE, MCP_SERVER_URL, SUPABASE_URL, SUPABASE_SECRET_KEY. Set DEBUG=false. Set CORS_ORIGINS to the required browser origins. Store credentials in the hosting provider secret store, never the image.

AUTH0_AUDIENCE must exactly match the Auth0 API identifier; it need not change simply because the hostname changes. MCP_SERVER_URL must be the final public HTTPS base URL. Machine tokens must be requested for the configured audience.

GET /health is a public process-liveness endpoint and does not assert database or Auth0 readiness. MCP operations remain authenticated at /mcp. Verify protected-resource metadata, valid-token tool calls, invalid-token rejection and a database-backed workflow after deployment.

Before exposing the service, verify the MCP SDK host/origin protections allow the final hostname without disabling them globally. Record the deployed commit and rollback target. A successful health check alone is not a completed release check.

No hosting provider or paid plan has been selected yet. The Docker image must be built and smoke-tested on a Docker-capable environment before deployment.

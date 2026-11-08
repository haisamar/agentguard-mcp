# AgentGuard MCP hosting

The frontend and this Python ASGI MCP service are separate Vercel projects.
The backend entrypoint is `app.py`, configured by `[tool.vercel]` in
`pyproject.toml`. Runtime dependencies come from the committed, hash-pinned
`requirements.txt` exported from `uv.lock`. See DEPENDENCIES.md for update commands.

## Container

Build with `docker build -t agentguard-mcp .` and run with `docker run --rm --env-file .env -p 3001:3001 agentguard-mcp`.

The container runs as a non-root user, listens on 0.0.0.0, and respects PORT. Environment files are excluded from the build context.

Required runtime configuration: AUTH0_DOMAIN, AUTH0_AUDIENCE, MCP_SERVER_URL, SUPABASE_URL, SUPABASE_SECRET_KEY. Set DEBUG=false. Set CORS_ORIGINS to the required browser origins. Store credentials in the hosting provider secret store, never the image.

AUTH0_AUDIENCE must exactly match the Auth0 API identifier; it need not change simply because the hostname changes. MCP_SERVER_URL must be the final public HTTPS base URL. Machine tokens must be requested for the configured audience.

GET /health is a public process-liveness endpoint and does not assert database or Auth0 readiness. MCP operations remain authenticated at /mcp. Verify protected-resource metadata, valid-token tool calls, invalid-token rejection and a database-backed workflow after deployment.

Before exposing the service, verify the MCP SDK host/origin protections allow the final hostname without disabling them globally. Record the deployed commit and rollback target. A successful health check alone is not a completed release check.

See [HOSTED-REHEARSAL.md](HOSTED-REHEARSAL.md) for an isolated setup and smoke-test procedure. For a credential-free empty-database rehearsal, use [the local evaluator](evaluation/README.md).

Current public MCP endpoint: https://agentguard-mcp-wine.vercel.app/mcp.
Vercel hosting has been configured; this document does not assert availability
or that local dependency changes have been deployed. The Docker image is an
alternative deployment artifact and still requires a Docker-capable build and
smoke test before use.

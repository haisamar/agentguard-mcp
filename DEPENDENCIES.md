# Dependency verification — Phase 1

Checked against PyPI on November 5, 2026. Direct dependencies use the latest
published releases: MCP 2.3.0, Starlette 1.10.0, Uvicorn 0.54.0, Supabase 2.34.0,
python-dotenv 1.2.4, and auth0-api-python 1.0.0b10. Auth0's newest release is
still a beta; it is explicitly pinned rather than described as a stable GA SDK.

`pyproject.toml` is the authoritative declaration. `uv.lock` resolves the
transitive graph. `requirements.txt` is a hash-pinned export used by Vercel,
the container, and CI. The resolver is uv 0.13.7 and package build backend is
poetry-core 2.5.0. CI/deployment target Python 3.12.

## Latest-version constraints

The resolved graph uses the newest releases permitted by upstream packages.
Two installed packages cannot use their newest majors:

| Package | Installed | Latest checked | Upstream constraint |
| --- | --- | --- | --- |
| ada-url | 1.32.0 | 4.0.0 | auth0-api-python requires `<2` |
| websockets | 15.0.1 | 17.4 | Supabase realtime requires `<16` |

Do not bypass these requirements with an incompatible forced installation.
Update them when the owning packages publish compatible releases. All 55
installed third-party packages were checked against PyPI version-specific
advisory metadata; no advisory matches remained after the refresh. This is
not proof of absence of vulnerabilities or verification of deployed versions.

## MCP v2 migration

- Replaced FastMCP with MCPServer and updated Context imports.
- Transport settings now live on streamable_http_app(), retaining explicit
  host/origin allowlists and stateless legacy HTTP behavior.
- Tool annotations use the v2 snake_case fields.
- Handler tests and actual ASGI tests cover authenticated tool dispatch,
  machine approval rejection, public metadata, unauthenticated rejection,
  and host/origin enforcement. Some transport cases use mocked claims. The
  signed-token cases use the SDK verifier with real RSA signatures and local
  discovery/JWKS fixtures. Database writes are mocked in those transport tests.

The Auth0 SDK emits an Authlib JOSE deprecation warning. Its dependency allows
Authlib 1.x, which remains supported by that SDK; no custom cryptography is added.

## Regeneration

```sh
uv lock --upgrade
uv export --frozen --no-dev --no-emit-project --output-file requirements.txt
uv sync --frozen
python -m unittest discover -s tests -v
```

CI additionally checks that exporting the lock does not change committed
requirements. See the [evidence index](SUBMISSION-EVIDENCE.md) for separate
hosted and local verification.

# Orkivo backend

FastAPI modular monolith. Modules today: `auth` (sessions), `users` (accounts and
the platform role), `workspaces` (tenants, membership, invitations) and `tasks`
(the first domain module), on top of SQLite sandbox mode; PostgreSQL remains the
canonical target.

Quickstart from this directory:

```bash
uv sync
cp .env.example .env           # optional; the defaults run the SQLite sandbox
uv run alembic upgrade head    # creates/updates the local database
uv run uvicorn app.main:app --reload --port 8000
```

## Layout

``` text
app/core/        settings, engine, session
app/api/v1/      router composition + health
app/modules/     auth, users, workspaces, tasks — each: router → service → repository
app/shared/      error payload, time helpers
migrations/      Alembic (every revision reviewed and reversible)
tests/           unit/ and api/, isolated temp SQLite per test
```

## Tenancy rules

Access to tenant content comes from `workspace_members` and nothing else. Roles
are read from the database on every request, so a demotion or a revocation takes
effect at once. The last owner cannot be demoted or removed, ownership cannot be
invited, personal workspaces refuse invitations, and a caller who is not in a
tenant is answered with the not-found shape rather than a forbidden one.
`tests/unit/test_workspaces_service.py` and `tests/api/test_workspaces_api.py`
are where each of those is pinned.

## Configuration that affects authentication

From `.env` / the environment (annotated list in `.env.example`):

- `SECRET_KEY` — HMAC signing key for access tokens, at least 32 characters.
  Optional in `development`, where an ephemeral per-process key is generated so
  signing material never lands in source control; **required** elsewhere, where
  the app refuses to start without one.
- `ACCESS_TOKEN_TTL_MINUTES` (15) and `REFRESH_TOKEN_TTL_DAYS` (30).
- `FIRST_OPERATOR_EMAIL` — the only account the backend will promote to platform
  operator, and only while none exists. Set it, sign in once, then clear it. It
  grants no tenancy: company authority comes only from membership.
- `COOKIE_SECURE` / `COOKIE_DOMAIN` — Secure cookies are on outside the local
  http sandbox; cookies are host-only unless a domain is given.
- `CORS_ORIGINS` — must include the origin serving the dashboard. The browser has
  to reach the API on the **same host name** (`localhost`, not `127.0.0.1`):
  cookies are per-host, so mixing the two reads as signed out.

## Quality gates

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run alembic upgrade head && uv run alembic check   # schema must equal models
```

See the root `README.md`, `docs/architecture/decisions/` and the architecture doc.

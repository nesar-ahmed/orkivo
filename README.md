# Orkivo

**Think. Organize. Build.** — a work management platform for tasks, projects
and insights. AI-assisted features are planned for later versions.

This repository is the **baseline**: multi-tenant accounts, sessions and
authorization, one domain module (`tasks`) behind a layered structure, plus a
feature-oriented Next.js frontend that consumes it. It is early-stage and meant
to run locally.

``` text
orkivo/
├── frontend/   Next.js 16 (App Router) + TypeScript + Tailwind v4
├── backend/    FastAPI + SQLAlchemy 2 + Alembic (managed with uv)
├── docs/       architecture record and decision logs (ADRs)
└── .gitignore
```

## What is in the baseline

Backend (`backend/`, modular monolith):

- `app/core/` — validated settings (`.env` / environment) and SQLAlchemy
  engine/session plumbing.
- `app/api/v1/` — versioned router composition + `GET /api/v1/health`.
- `app/modules/auth/` — registration, login, refresh rotation, logout; Argon2id
  password hashing, short-lived access JWTs, opaque revocable refresh sessions,
  cookie transport and the CSRF guard.
- `app/modules/users/` — accounts, the **platform** role (`user` / `operator`),
  own-profile edits and the operator's account directory.
- `app/modules/workspaces/` — the tenant: personal and company workspaces,
  membership with `owner` / `admin` / `member` roles, addressed invitations,
  and the operator's tenant console.
- `app/modules/tasks/` — the first domain module, with the structure every module
  follows: `router` → `service` (use cases, transaction boundary) →
  `repository` (SQLAlchemy queries), plus `models`, `schemas`, `dependencies`,
  `exceptions`.
- Consistent error contract:
  `{"error": {"code", "message", "details"}}` — including failures raised by the
  framework itself (405, unmatched 404, request validation).
- UUID primary keys, timezone-aware UTC timestamps, enums stored as values,
  database check constraints for hard invariants, indexed columns, paginated and
  filtered list endpoints.
- Alembic migrations (`migrations/`), each one reviewed and reversible; pytest
  unit + API tests (isolated temporary SQLite per test); Ruff + mypy gates.

Frontend (`frontend/`):

- App Router. Public surface: `/` (landing), `/login`, `/register`. The product
  lives under `/app`: `/app/dashboard`, `/app/workspaces`,
  `/app/workspaces/{id}/people`, `/app/profile`, and the operator console at
  `/app/platform/tenants` and `/app/platform/accounts`.
- `proxy.ts` keeps `/app/**` away from visitors with no session cookie and sends
  signed-in people out of the public screens. It is convenience only: the `/app`
  layout re-reads the caller from the API before it renders, and the backend
  refuses every unauthorized request.
- Centralized design tokens in `app/globals.css` (Tailwind v4 `@theme`, light +
  dark — the only place colors are defined); shared primitives in
  `components/ui`; feature code in `features/{auth,users,workspaces,tasks}`;
  all fetches through `lib/api/client.ts`.
- Loading (pending), empty, error and permission-denied states handled;
  keyboard-accessible controls, visible focus, `aria-live` alerts.

## Tenancy: two role axes, one rule

A **workspace is the tenant**, and every account has exactly one private
workspace created with it in the same transaction. A company is the same table
with `kind = "team"`, a unique slug, and more than one member. So there is one
authorization question everywhere: *is this actor a member of this tenant, at
what role* — and a non-member is answered with the same 404 shape as a tenant
that does not exist, so the API cannot enumerate other companies.

| Axis | Column | Values | Decides |
| --- | --- | --- | --- |
| Platform | `users.platform_role` | `user`, `operator` | Who may read the account directory, change platform roles, suspend tenants |
| Tenant | `workspace_members.role` | `owner`, `admin`, `member` | Who may rename a company, invite, remove, change roles inside it |

Nothing bridges them. An operator has **no** membership in any tenant, and no
endpoint lets an operator read a tenant's tasks, descriptions or comments — the
console sees kind, name, slug, status, member count and dates. Rules worth
knowing:

- Only an owner changes roles; ownership can be transferred but never *invited*.
- A tenant always keeps at least one owner: the last one cannot be demoted or
  removed.
- Admins may remove members and other admins, never an owner.
- Personal workspaces refuse invitations — that is what makes them private.
- `FIRST_OPERATOR_EMAIL` bootstraps the first operator and grants no tenancy.

**Invitations are addressed, not delivered.** An admin adds an email; the offer
waits in that address's profile, and joining is the addressee's own act. No mail
transport is needed today, and the same row is what a mail transport would send
later. See `docs/architecture/decisions/0001-multi-tenant-workspaces.md`.

## Authentication model

Both credentials are `HttpOnly` `SameSite=Lax` cookies; no token is ever returned
in a body or read by a script (ADR-0002).

| Cookie | Content | Lifetime | Path |
| --- | --- | --- | --- |
| `orkivo_access` | signed JWT (`sub`, `sid`) | `ACCESS_TOKEN_TTL_MINUTES` (15) | `/` |
| `orkivo_refresh` | opaque token, stored as a SHA-256 digest | `REFRESH_TOKEN_TTL_DAYS` (30) | `/api/v1/auth` |

- **No role in the token** — the account is re-read per request, so revocation and
  demotion take effect immediately.
- **Rotation with reuse detection** — refreshing spends a session; presenting an
  already-spent token revokes the whole family.
- **CSRF** — `SameSite=Lax` plus a required `X-Orkivo-Request: 1` header on every
  cookie-authenticated state change; `Authorization: Bearer` is exempt.
- **Generic failures** — wrong password and unknown email answer identically.
- **Renewal happens in the browser.** The refresh cookie is path-scoped to the
  API, so a navigation never carries it and `proxy.ts` cannot renew. A 401 on a
  browser call renews once and replays (single-flight, with a cross-tab claim so
  two tabs cannot look like theft), and the login screen tries the same before
  asking for a password.

## Quickstart

Prerequisites: [uv](https://docs.astral.sh/uv/) and Node.js 20+.

Backend (port 8000):

```bash
cd backend
cp .env.example .env        # optional; defaults already point at the SQLite sandbox
uv sync
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8000
```

Interactive API docs: <http://127.0.0.1:8000/docs>

Frontend (port 3000):

```bash
cd frontend
npm install
npm run dev
```

Open <http://localhost:3000>.

**Use `localhost`, not `127.0.0.1`, for both.** Cookies are stored per host and
ignore the port, so an API reached under a different host name than the
dashboard is served from means the browser never attaches the session.

### Signing in for the first time

Registration always creates an ordinary account, and no request body can name a
role. To get the first operator:

1. Set `FIRST_OPERATOR_EMAIL=<an address you control>` in `backend/.env`.
2. Register that address from the landing page (**Create account**) and sign in.
   It is promoted on that first sign-in, and `Platform` appears in the
   navigation.
3. **Clear the setting.** It grants nothing once any operator exists, but leaving
   it set is needless configuration.

Companies don't need an operator: any account can open one from **Workspaces**
and becomes its owner. Without the setting, Orkivo runs with everyone as an
ordinary account and every other feature still works.

## Quality gates

Backend (run from `backend/`):

```bash
uv run pytest                     # unit + API tests
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run alembic upgrade head && uv run alembic check   # schema == models
```

`alembic check` is worth running after any model change: it caught a renamed
column that would have been too short for `operator` on PostgreSQL.

Frontend (run from `frontend/`):

```bash
npm run lint
npm run build                 # includes TypeScript checks
```

## Roadmap

1. **Scope tasks to a workspace** — `tasks.workspace_id`, backfilled from each
   owner's personal tenant, then filtered by membership. Until this lands a
   company has members but no shared content.
2. `projects` inside a workspace, with the board view (drag plus a keyboard
   route to the same move).
3. `comments` and the append-only `activity` trail.
4. PostgreSQL as the default target, with integration tests against it.
5. Challenge 2's wider role set (manager/developer/viewer) —
   `workspace_members.role` is the documented extension point.
6. AI-assisted features behind a provider-independent interface, so no vendor is
   required to run Orkivo.

Already shipped in this baseline: `auth`, `users`, `workspaces`, and
authorization on every endpoint.

## Known limitations

- **Tasks are not workspace-scoped yet.** They are scoped to `owner_id`, which is
  equivalent to the owner's personal tenant. Shared work inside a company is the
  next change.
- **No self-service password or email change.** The backend has no such endpoint,
  so `/profile` edits the display name only.
- **No login rate limiting.** `429 / RATE_LIMITED` is mapped in the error contract
  but nothing can emit it yet — worth closing before inviting strangers to sign up.
- **No session list or "sign out everywhere"**, because the API exposes no session
  listing.
- **Invitations trust control of the email address.** Fine for a self-hosted
  baseline; revisit before public registration at scale (ADR-0001).
- **SQLite sandbox mode is the default**; PostgreSQL is the canonical target.
- **No frontend test tooling** (Vitest/Playwright) and no `Makefile`, CI workflow
  or `docker-compose.yml` yet.
- Only synthetic sample data is used anywhere in this repository.

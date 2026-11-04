# Orkivo

**Think. Organize. Build.** — a work management platform for tasks, projects
and insights. AI-assisted features are planned for later versions.

This repository is the **minimal baseline**: exactly **one backend module
(`tasks`)** behind a layered structure, plus a small feature-oriented Next.js
frontend that consumes it. It is early-stage and meant to run locally.

``` text
orkivo/
├── frontend/   Next.js 16 (App Router) + TypeScript + Tailwind v4
├── backend/    FastAPI + SQLAlchemy 2 + Alembic (managed with uv)
└── .gitignore
```

## What is in the baseline

Backend (`backend/`, modular monolith):

- `app/core/` — validated settings (`.env` / environment) and SQLAlchemy
  engine/session plumbing.
- `app/api/v1/` — versioned router composition + `GET /api/v1/health`.
- `app/modules/tasks/` — the single module, with a consistent internal
  structure: `router` → `service` (use cases, transaction boundary) →
  `repository` (SQLAlchemy queries), plus `models`, `schemas`,
  `dependencies`, `exceptions`.
- Consistent error contract:
  `{"error": {"code", "message", "details"}}`.
- UUID primary keys, timezone-aware UTC `created_at`/`updated_at`, enums
  stored as values, DB check constraint on title, indexed columns,
  paginated/filtered list endpoint (`status`, `priority`, `search`,
  `page`, `page_size`).
- Alembic migrations (`migrations/`), initial revision committed; pytest
  unit + API tests (isolated temp SQLite per test); Ruff + mypy gates.

Frontend (`frontend/`):

- App Router with a route group `(dashboard)` and a shared shell layout.
- Centralized design tokens in `app/globals.css` (Tailwind v4 `@theme`,
  light + dark, single brand/semantic palette — the only place colors are
  defined).
- Shared primitives in `components/ui` (Button, Badge, Input, Select,
  Textarea, EmptyState) — no business logic.
- `features/tasks/` with `api/` queries & mutations, `components/`
  (task-list, task-card, task-form) and display utils; typed contracts in
  `types/`; all fetch calls go through `lib/api/client.ts`.
- Loading (pending), empty, and error states handled; keyboard-accessible
  controls, visible focus, `aria-live` alerts; status moves have an
  accessible non-drag alternative (select).

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

Open <http://localhost:3000> — the dashboard reads live from the API.

## Quality gates

Backend (run from `backend/`):

```bash
uv run pytest                 # unit + api tests
uv run ruff check . && uv run ruff format --check .
uv run mypy app
uv run alembic upgrade head   # from a clean database
```

Frontend (run from `frontend/`):

```bash
npm run lint
npm run build                 # includes TypeScript checks
```

## Roadmap

Roughly in this order:

1. `auth` / `users` / `workspaces` modules, with authorization enforced on
   every endpoint.
2. Scope tasks to a workspace and project (foreign keys plus migrations).
3. PostgreSQL as the default target, with integration tests against it.
4. Projects, notes and workflows around the existing task module.
5. AI-assisted features — drafting, planning and summaries — behind a
   provider-independent interface, so no vendor is required to run Orkivo.

## Known limitations of this minimal baseline

- **No authentication/authorization yet.** The `tasks` module is the only
  module, so nothing here should be exposed beyond `localhost` until
  `auth`/`users`/`workspaces` land.
- **SQLite sandbox mode is the default.** PostgreSQL remains the canonical
  target; PostgreSQL integration tests are a later stage. Set `DATABASE_URL`
  to a PostgreSQL URL to switch.
- Tasks are not yet scoped to a workspace/project; those foreign keys arrive
  with the corresponding modules.
- Frontend test tooling (Vitest/Playwright) and a `Makefile` are not part of
  this baseline.
- Only synthetic sample data is used anywhere in this repository.

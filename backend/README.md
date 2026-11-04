# Orkivo backend

FastAPI modular monolith. Current baseline implements one module (`tasks`) on
top of SQLite sandbox mode; PostgreSQL remains the canonical target.

Quickstart from this directory:

```bash
uv sync
uv run alembic upgrade head        # creates/updates the local database
uv run uvicorn app.main:app --reload --port 8000
```

Quality gates:

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
uv run mypy app
```

See the root `README.md` and the internal architecture doc.

"""Health and readiness endpoint (architecture doc section 13)."""

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.v1.deps import DbSession

router = APIRouter(tags=["health"])


@router.get("/health")
def health(db: DbSession) -> JSONResponse:
    """Return process health plus a database connectivity check."""
    try:
        db.execute(text("SELECT 1"))
        database = "ok"
        status_code = 200
        status = "ok"
    except SQLAlchemyError:
        db.rollback()
        database = "unavailable"
        status_code = 503
        status = "degraded"
    return JSONResponse(status_code=status_code, content={"status": status, "database": database})

"""API-level dependencies shared by v1 routers."""

from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import Session

from app.core.db import get_db

DbSession = Annotated[Session, Depends(get_db)]

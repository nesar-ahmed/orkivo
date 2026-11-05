"""Pydantic request/response contracts for the auth module.

Tokens are transported in httpOnly cookies, so no contract here carries token
material, and the password hash is never part of a response
(architecture doc section 7.1).

Note: these models deliberately do *not* strip surrounding whitespace ---
silently rewriting a password would lock people out of accounts whose password
starts or ends with a space. Email normalization happens in the service layer.
"""

from datetime import datetime
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field

from app.modules.auth.passwords import PASSWORD_MAX_LENGTH, PASSWORD_MIN_LENGTH
from app.modules.users.schemas import UserRead

Password = Annotated[
    str,
    # ``repr=False`` keeps the value out of exception text and log lines.
    Field(min_length=PASSWORD_MIN_LENGTH, max_length=PASSWORD_MAX_LENGTH, repr=False),
]

RegistrationDisplayName = Annotated[str | None, Field(default=None, min_length=1, max_length=100)]


class RegisterRequest(BaseModel):
    """Input contract for creating an account."""

    email: EmailStr
    password: Password
    display_name: RegistrationDisplayName = None


class LoginRequest(BaseModel):
    """Input contract for starting a session."""

    email: EmailStr
    password: Password


class SessionResponse(BaseModel):
    """Result of a successful login or refresh."""

    user: UserRead
    session_id: UUID
    access_token_expires_at: datetime

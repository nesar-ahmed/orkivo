"""Domain/application exceptions for the auth module.

Messages are deliberately generic: authentication failures must not reveal
whether an account exists (architecture doc section 9).
"""


class AuthenticationError(Exception):
    """No valid credentials were supplied for a protected operation."""

    code = "UNAUTHORIZED"
    message = "Sign in is required to use this endpoint."

    def __init__(self, message: str | None = None) -> None:
        super().__init__(message or self.message)


class InvalidCredentialsError(AuthenticationError):
    """Email/password pair did not match. Same message for both halves."""

    code = "INVALID_CREDENTIALS"
    message = "Email or password is incorrect."

    def __init__(self) -> None:
        super().__init__(self.message)


class SessionError(Exception):
    """The refresh session is missing, expired, revoked, or reused."""

    code = "SESSION_INVALID"
    message = "Your session is no longer valid. Please sign in again."


class AuthorizationError(Exception):
    """The authenticated user may not perform this operation."""

    code = "FORBIDDEN"
    message = "You do not have access to this resource."


class CsrfCheckFailedError(AuthorizationError):
    """A cookie-authenticated state change did not carry the CSRF header."""

    code = "CSRF_CHECK_FAILED"
    message = "This request was rejected by the session protection policy."


class AccountDisabledError(Exception):
    """The credentials were right, but a platform operator disabled the account.

    Only ever raised *after* the password matched, so it reveals nothing to
    someone guessing; the owner of the account learns why they cannot get in.
    """

    code = "ACCOUNT_DISABLED"
    message = "This account has been disabled. Contact support if you think this is a mistake."

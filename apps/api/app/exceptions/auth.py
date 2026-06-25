"""Custom authentication exceptions."""


class AuthException(Exception):  # noqa: N818
    """Base exception for all authentication-related errors."""

    status_code: int = 400
    detail: str = "Authentication error."

    def __init__(self, detail: str | None = None):
        super().__init__(detail or self.detail)
        if detail is not None:
            self.detail = detail


class InvalidCredentialsException(AuthException):
    """Raised when email or password is incorrect."""

    status_code: int = 401
    detail: str = "Invalid credentials."


class UserAlreadyExistsException(AuthException):
    """Raised when trying to register an email that is already registered."""

    status_code: int = 409
    detail: str = "An account with this email already exists."


class SessionExpiredException(AuthException):
    """Raised when a refresh token session has expired."""

    status_code: int = 401
    detail: str = "Session has expired or is invalid."


class AccountLockedException(AuthException):
    """Raised when an account is temporarily locked due to failed login attempts."""

    status_code: int = 403
    detail: str = "Account is temporarily locked. Please try again later."


class EmailNotVerifiedException(AuthException):
    """Raised when trying to login but email is not verified."""

    status_code: int = 403
    detail: str = "Email is not verified."


class InvalidRefreshTokenException(AuthException):
    """Raised when a refresh token is invalid, malformed, or reused."""

    status_code: int = 401
    detail: str = "Invalid refresh token."


class PasswordValidationError(AuthException):
    """Raised when password validation fails."""

    status_code: int = 400
    detail: str = "Password does not meet requirements."


class EmailAlreadyVerifiedException(AuthException):
    """Raised when trying to verify or resend verification to an already verified email."""

    status_code: int = 400
    detail: str = "Email is already verified."

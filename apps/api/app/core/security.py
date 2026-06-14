"""Security utilities: password hashing, JWT token management, password validation."""

from datetime import UTC, datetime, timedelta
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings
from app.exceptions.auth import PasswordValidationError

# Use argon2 for password hashing (OWASP recommendation)
pwd_context = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(password: str) -> str:
    """Hash a plaintext password using Argon2."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against an Argon2 hash."""
    return pwd_context.verify(plain_password, hashed_password)


def validate_password(password: str) -> None:
    """Enforce password validation constraints.

    Enforces:
    - Minimum length: 8
    - Maximum length: 128

    Raises:
        PasswordValidationError: If the password is invalid.
    """
    if not password:
        raise PasswordValidationError("Password cannot be empty.")
    if len(password) < 8:
        raise PasswordValidationError("Password must be at least 8 characters long.")
    if len(password) > 128:
        raise PasswordValidationError("Password cannot be longer than 128 characters.")


def create_access_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a short-lived JWT access token containing standard claims.

    Access Token Claims:
    - sub (user_id)
    - email
    - role
    - type: "access"
    - exp
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    )
    to_encode.update({"exp": expire, "type": "access"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def create_refresh_token(data: dict[str, Any], expires_delta: timedelta | None = None) -> str:
    """Create a long-lived JWT refresh token containing sub and type.

    Refresh Token Claims:
    - sub (user_id)
    - type: "refresh"
    - exp
    """
    to_encode = data.copy()
    expire = datetime.now(UTC) + (
        expires_delta or timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
    )
    to_encode.update({"exp": expire, "type": "refresh"})
    return jwt.encode(to_encode, settings.SECRET_KEY, algorithm=settings.ALGORITHM)


def decode_token(token: str) -> dict[str, Any] | None:
    """Decode and validate a JWT token. Returns payload or None if invalid."""
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        return payload
    except JWTError:
        return None

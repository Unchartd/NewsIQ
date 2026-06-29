import hashlib
import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.exceptions.auth import (
    AuthException,
    EmailAlreadyVerifiedException,
    InvalidCredentialsException,
)
from app.models.user import User
from app.services.auth_service import AuthService


@pytest.fixture
def mock_redis():
    """Mock Redis client in cache_service."""
    client = AsyncMock()
    client.get = AsyncMock(return_value=None)
    client.set = AsyncMock(return_value=True)
    client.incr = AsyncMock(return_value=1)
    client.expire = AsyncMock(return_value=True)
    return client


@pytest.mark.asyncio
async def test_verify_email_success(mock_db_session):
    """Test verification succeeds using raw token matching hashed token in DB."""
    raw_token = "my-secret-token"
    hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        email_verified=False,
        email_verification_token=hashed_token,
        email_verification_expiry=datetime.now(UTC).replace(tzinfo=None) + timedelta(hours=24),
    )

    # Mock DB query
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    auth_service = AuthService(mock_db_session)
    verified_user = await auth_service.verify_email(raw_token)

    assert verified_user.email_verified is True
    assert verified_user.email_verification_token is None
    assert verified_user.email_verification_expiry is None


@pytest.mark.asyncio
async def test_verify_email_invalid_token(mock_db_session):
    """Test verification fails with an invalid token."""
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_res

    auth_service = AuthService(mock_db_session)

    with pytest.raises(InvalidCredentialsException):
        await auth_service.verify_email("invalid-token")


@pytest.mark.asyncio
async def test_resend_verification_already_verified(mock_db_session):
    """Test resending verification to an already verified email raises EmailAlreadyVerifiedException."""
    user = User(
        id=uuid.uuid4(),
        email="verified@example.com",
        email_verified=True,
    )

    # Mock DB query
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    auth_service = AuthService(mock_db_session)

    with pytest.raises(EmailAlreadyVerifiedException):
        await auth_service.request_email_verification("verified@example.com")


@pytest.mark.asyncio
async def test_resend_verification_cooldown_rate_limit(mock_db_session, mock_redis):
    """Test that requesting verification within 60s cooldown raises AuthException."""
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        email_verified=False,
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    # Mock Redis client returned by cache_service._redis
    mock_redis.get.return_value = "1"  # Token rate-limited cooldown active

    auth_service = AuthService(mock_db_session)

    with (
        patch("app.services.auth_service.cache_service._redis", mock_redis),
    ):
        with pytest.raises(AuthException) as exc:
            await auth_service.request_email_verification("user@example.com")

        assert "Please wait at least 60 seconds" in str(exc.value)


@pytest.mark.asyncio
async def test_resend_verification_ip_rate_limit(mock_db_session, mock_redis):
    """Test that requesting too many verification emails from the same IP raises AuthException."""
    user = User(
        id=uuid.uuid4(),
        email="user@example.com",
        email_verified=False,
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    # Mock Redis client returned by cache_service._redis
    # IP count is 5 (max allowed is 5 per hour)
    mock_redis.get.side_effect = [None, "5"]

    auth_service = AuthService(mock_db_session)

    with (
        patch("app.services.auth_service.cache_service._redis", mock_redis),
    ):
        with pytest.raises(AuthException) as exc:
            await auth_service.request_email_verification("user@example.com", ip_address="192.168.1.1")

        assert "Too many verification requests from this IP" in str(exc.value)

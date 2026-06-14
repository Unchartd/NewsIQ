"""Unit tests for the refactored authentication module."""

import uuid
from datetime import UTC, datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException

from app.api.v1.auth import (
    forgot_password,
    login,
    logout,
    logout_all,
    refresh_token,
    register,
    reset_password,
    verify_email,
    verify_reset_token,
    get_sessions,
    revoke_session,
)
from app.exceptions.auth import (
    AccountLockedException,
    EmailNotVerifiedException,
    InvalidCredentialsException,
    InvalidRefreshTokenException,
    SessionExpiredException,
    UserAlreadyExistsException,
)
from app.models.user import User
from app.models.session import Session
from app.schemas.auth import (
    LoginRequest,
    RegisterRequest,
    ResetPasswordRequest,
    ForgotPasswordRequest,
)


@pytest.fixture
def mock_request():
    request = MagicMock()
    request.client.host = "127.0.0.1"
    request.headers = {"user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"}
    request.cookies = {}
    return request


@pytest.fixture
def mock_response():
    response = MagicMock()
    response.set_cookie = MagicMock()
    response.delete_cookie = MagicMock()
    return response


@pytest.mark.asyncio
async def test_register_success(mock_db_session, mock_request, mock_response):
    """Test successful user registration flow."""
    body = RegisterRequest(
        name="John Doe",
        email="john@example.com",
        password="securepassword123",
        confirm_password="securepassword123",
    )

    # Mock no existing user
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_execute_res

    # Mock token generation and cookie setting
    with (
        patch("app.services.auth_service.secrets.token_urlsafe", return_value="verifytoken"),
        patch("app.services.auth_service.create_access_token", return_value="accesstoken"),
        patch("app.services.auth_service.create_refresh_token", return_value="refreshtoken"),
    ):
        res = await register(body, mock_request, mock_response, mock_db_session)

        assert res.access_token == "accesstoken"
        assert res.user.email == "john@example.com"
        mock_response.set_cookie.assert_called_once_with(
            key="refresh_token",
            value="refreshtoken",
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=30 * 24 * 60 * 60,
            path="/",
        )


@pytest.mark.asyncio
async def test_register_duplicate_email(mock_db_session, mock_request, mock_response):
    """Test register fails when email already exists."""
    body = RegisterRequest(
        name="John Doe",
        email="john@example.com",
        password="securepassword123",
        confirm_password="securepassword123",
    )

    # Mock user exists
    existing_user = User(email="john@example.com", role="user", subscription_plan="free")
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = existing_user
    mock_db_session.execute.return_value = mock_execute_res

    with pytest.raises(UserAlreadyExistsException):
        await register(body, mock_request, mock_response, mock_db_session)


@pytest.mark.asyncio
async def test_login_success(mock_db_session, mock_request, mock_response):
    """Test successful login."""
    body = LoginRequest(email="john@example.com", password="securepassword123")

    from app.core.security import hash_password
    hashed = hash_password("securepassword123")

    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        password_hash=hashed,
        email_verified=True,
        status="active",
        role="user",
        subscription_plan="free",
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    with (
        patch("app.services.auth_service.create_access_token", return_value="accesstoken"),
        patch("app.services.auth_service.create_refresh_token", return_value="refreshtoken"),
    ):
        res = await login(body, mock_request, mock_response, mock_db_session)
        assert res.access_token == "accesstoken"
        assert user.failed_login_attempts == 0
        assert user.last_login_at is not None


@pytest.mark.asyncio
async def test_login_invalid_credentials(mock_db_session, mock_request, mock_response):
    """Test login fails on incorrect password."""
    body = LoginRequest(email="john@example.com", password="wrongpassword")

    from app.core.security import hash_password
    hashed = hash_password("securepassword123")

    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        password_hash=hashed,
        email_verified=True,
        status="active",
        role="user",
        subscription_plan="free",
        failed_login_attempts=0,
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    with pytest.raises(InvalidCredentialsException):
        await login(body, mock_request, mock_response, mock_db_session)

    assert user.failed_login_attempts == 1


@pytest.mark.asyncio
async def test_login_account_lockout(mock_db_session, mock_request, mock_response):
    """Test that 5 failed attempts lock the account."""
    body = LoginRequest(email="john@example.com", password="wrongpassword")

    from app.core.security import hash_password
    hashed = hash_password("securepassword123")

    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        password_hash=hashed,
        email_verified=True,
        status="active",
        role="user",
        subscription_plan="free",
        failed_login_attempts=4,  # Next failure will trigger lockout
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    with pytest.raises(InvalidCredentialsException):
        await login(body, mock_request, mock_response, mock_db_session)

    assert user.failed_login_attempts == 5
    assert user.locked_until is not None

    # Verify locked out check
    user.locked_until = datetime.now(UTC).replace(tzinfo=None) + timedelta(minutes=10)
    with pytest.raises(AccountLockedException):
        await login(body, mock_request, mock_response, mock_db_session)


@pytest.mark.asyncio
async def test_login_email_unverified(mock_db_session, mock_request, mock_response):
    """Test login fails if email is not verified."""
    body = LoginRequest(email="john@example.com", password="securepassword123")

    from app.core.security import hash_password
    hashed = hash_password("securepassword123")

    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        password_hash=hashed,
        email_verified=False,
        status="active",
        role="user",
        subscription_plan="free",
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    with pytest.raises(EmailNotVerifiedException):
        await login(body, mock_request, mock_response, mock_db_session)


@pytest.mark.asyncio
async def test_refresh_token_rotation(mock_db_session, mock_request, mock_response):
    """Test successful token rotation and session creation."""
    mock_request.cookies = {"refresh_token": "tokenA"}

    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        status="active",
        role="user",
        subscription_plan="free",
    )
    session = Session(
        id=uuid.uuid4(),
        user_id=user.id,
        token_hash="hashA",
        expires_at=datetime.now(UTC).replace(tzinfo=None) + timedelta(days=1),
        user=user,
    )

    # Mock decode_token to return valid payload
    with (
        patch("app.services.auth_service.decode_token", return_value={"sub": str(user.id), "type": "refresh"}),
        patch("app.services.session_service.SessionService.hash_token", return_value="hashA"),
        patch("app.services.session_service.SessionRepository.get_by_token_hash", return_value=session),
        patch("app.services.session_service.SessionRepository.delete") as mock_delete,
        patch("app.services.session_service.SessionRepository.create") as mock_create,
        patch("app.services.auth_service.create_access_token", return_value="accesstokenB"),
        patch("app.services.auth_service.create_refresh_token", return_value="tokenB"),
    ):
        res = await refresh_token(mock_request, mock_response, mock_db_session)
        assert res.access_token == "accesstokenB"
        mock_delete.assert_called_once()
        mock_create.assert_called_once()
        mock_response.set_cookie.assert_called_once_with(
            key="refresh_token",
            value="tokenB",
            httponly=True,
            secure=True,
            samesite="lax",
            max_age=30 * 24 * 60 * 60,
            path="/",
        )


@pytest.mark.asyncio
async def test_refresh_token_theft_revocation(mock_db_session, mock_request, mock_response):
    """Test that token reuse triggers revocation of all active sessions."""
    mock_request.cookies = {"refresh_token": "reused_token"}
    user_id = uuid.uuid4()

    with (
        patch("app.services.auth_service.decode_token", return_value={"sub": str(user_id), "type": "refresh"}),
        patch("app.services.session_service.SessionService.hash_token", return_value="reused_hash"),
        patch("app.services.session_service.SessionRepository.get_by_token_hash", return_value=None),
        patch("app.services.session_service.SessionRepository.delete_all_by_user_id") as mock_delete_all,
    ):
        with pytest.raises(HTTPException) as excinfo:
            await refresh_token(mock_request, mock_response, mock_db_session)

        assert excinfo.value.status_code == 401
        mock_delete_all.assert_called_once_with(user_id)


@pytest.mark.asyncio
async def test_logout_current_device(mock_db_session, mock_request, mock_response):
    """Test logging out deletes that specific session."""
    mock_request.cookies = {"refresh_token": "tokenA"}

    with (
        patch("app.services.session_service.SessionService.hash_token", return_value="hashA"),
        patch("app.services.session_service.SessionRepository.delete_by_token_hash") as mock_delete,
    ):
        res = await logout(mock_request, mock_response, mock_db_session)
        assert res.message == "Logged out successfully."
        mock_delete.assert_called_once_with("hashA")
        mock_response.delete_cookie.assert_called_once_with(key="refresh_token", path="/")


@pytest.mark.asyncio
async def test_logout_all_devices(mock_db_session, mock_response):
    """Test logout all devices deletes all user sessions."""
    user = User(id=uuid.uuid4(), role="user", subscription_plan="free")

    with patch("app.services.session_service.SessionRepository.delete_all_by_user_id") as mock_delete_all:
        res = await logout_all(mock_response, user, mock_db_session)
        assert res.message == "Logged out from all devices."
        mock_delete_all.assert_called_once_with(user.id)
        mock_response.delete_cookie.assert_called_once_with(key="refresh_token", path="/")


@pytest.mark.asyncio
async def test_password_reset_flow(mock_db_session):
    """Test full forgot-password and reset-password flow."""
    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        role="user",
        subscription_plan="free",
    )

    # 1. Forgot password request
    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    forgot_body = ForgotPasswordRequest(email="john@example.com")
    with patch("app.services.auth_service.secrets.token_urlsafe", return_value="resettoken"):
        res = await forgot_password(forgot_body, mock_db_session)
        assert "reset link has been sent" in res.message
        import hashlib
        assert user.password_reset_token == hashlib.sha256(b"resettoken").hexdigest()
        assert user.password_reset_expiry is not None

    # 2. Reset password
    reset_body = ResetPasswordRequest(token="resettoken", new_password="newsecurepassword123")
    with (
        patch("app.services.session_service.SessionRepository.delete_all_by_user_id") as mock_delete_all,
    ):
        res = await reset_password(reset_body, mock_db_session)
        assert res.message == "Password reset successfully."
        assert user.password_reset_token is None
        assert user.password_reset_expiry is None
        mock_delete_all.assert_called_once_with(user.id)


@pytest.mark.asyncio
async def test_email_verification(mock_db_session):
    """Test email verification flow."""
    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        email_verified=False,
        role="user",
        subscription_plan="free",
    )

    mock_execute_res = MagicMock()
    mock_execute_res.scalar_one_or_none.return_value = user
    mock_db_session.execute.return_value = mock_execute_res

    res = await verify_email(token="verifytoken", db=mock_db_session)
    assert res.message == "Email verified successfully."
    assert user.email_verified is True


@pytest.mark.asyncio
async def test_session_revocation(mock_db_session, mock_request):
    """Test retrieving active sessions and revoking a specific session."""
    user = User(
        id=uuid.uuid4(),
        email="john@example.com",
        role="user",
        subscription_plan="free",
    )
    session_id = uuid.uuid4()
    session = Session(id=session_id, user_id=user.id)

    # 1. Get sessions
    mock_execute_res = MagicMock()
    mock_execute_res.scalars.return_value.all.return_value = [session]
    mock_db_session.execute.return_value = mock_execute_res

    sessions_res = await get_sessions(mock_request, user, mock_db_session)
    assert len(sessions_res) == 1
    assert sessions_res[0].id == str(session_id)

    # 2. Revoke session
    mock_execute_res2 = MagicMock()
    mock_execute_res2.scalar_one_or_none.return_value = session
    mock_db_session.execute.return_value = mock_execute_res2

    with patch("app.services.session_service.SessionRepository.delete") as mock_delete:
        res = await revoke_session(session_id, user, mock_db_session)
        assert res.message == "Session revoked successfully."
        mock_delete.assert_called_once_with(session)

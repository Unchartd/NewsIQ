"""Auth API endpoints: register, login, logout, refresh, me, sessions, email/password workflows."""

import hashlib
import uuid

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_user
from app.exceptions.auth import AuthException
from app.models.user import User
from app.schemas.auth import (
    AuthResponse,
    ForgotPasswordRequest,
    LoginRequest,
    MessageResponse,
    RefreshResponse,
    RegisterRequest,
    ResetPasswordRequest,
    SessionResponse,
    UserResponse,
)
from app.schemas.user import ChangePasswordRequest
from app.services.auth_service import AuthService

router = APIRouter()


def _user_to_response(user: User) -> UserResponse:
    """Convert a User ORM model to a UserResponse schema."""
    return UserResponse(
        id=str(user.id),
        email=user.email,
        name=user.name,
        image_url=user.image_url,
        role=user.role,
        subscription_plan=user.subscription_plan,
        status=user.status,
        email_verified=user.email_verified,
        created_at=user.created_at.isoformat() if user.created_at else "",
    )


def _set_refresh_cookie(response: Response, refresh_token: str) -> None:
    """Set the refresh token as an HTTP-only cookie."""
    response.set_cookie(
        key="refresh_token",
        value=refresh_token,
        httponly=True,
        secure=not settings.DEBUG,  # HTTPS only in production
        samesite="lax",
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 24 * 60 * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def _set_access_cookie(response: Response, access_token: str) -> None:
    """Set the access token as an HTTP-only cookie for robust initial page loads."""
    response.set_cookie(
        key="access_token",
        value=access_token,
        httponly=True,
        secure=not settings.DEBUG,
        samesite="lax",
        max_age=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        path="/",
        domain=settings.COOKIE_DOMAIN,
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(
        key="refresh_token",
        path="/",
        secure=not settings.DEBUG,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
    )


def _clear_access_cookie(response: Response) -> None:
    """Clear the access token cookie."""
    response.delete_cookie(
        key="access_token",
        path="/",
        secure=not settings.DEBUG,
        samesite="lax",
        domain=settings.COOKIE_DOMAIN,
    )


@router.post("/register", response_model=AuthResponse, status_code=status.HTTP_201_CREATED)
async def register(
    body: RegisterRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Create a new user account."""
    if body.password != body.confirm_password:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Passwords do not match.",
        )

    auth_service = AuthService(db)
    user, access_token, refresh_token = await auth_service.register(
        name=body.name,
        email=body.email,
        password=body.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    _set_refresh_cookie(response, refresh_token)
    _set_access_cookie(response, access_token)

    return AuthResponse(
        access_token=access_token,
        user=_user_to_response(user),
    )


@router.post("/login", response_model=AuthResponse)
async def login(
    body: LoginRequest,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Authenticate with email and password."""
    auth_service = AuthService(db)
    user, access_token, refresh_token = await auth_service.login(
        email=body.email,
        password=body.password,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    _set_refresh_cookie(response, refresh_token)
    _set_access_cookie(response, access_token)

    return AuthResponse(
        access_token=access_token,
        user=_user_to_response(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token using rotating refresh token cookie."""
    refresh_token_cookie = request.cookies.get("refresh_token")
    if not refresh_token_cookie:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token.",
        )

    auth_service = AuthService(db)
    try:
        access_token, new_refresh_token, _ = await auth_service.rotate_refresh_token(
            refresh_token=refresh_token_cookie,
            ip_address=request.client.host if request.client else None,
            user_agent=request.headers.get("user-agent"),
        )
    except AuthException as e:
        _clear_refresh_cookie(response)
        _clear_access_cookie(response)
        raise HTTPException(
            status_code=e.status_code,
            detail=e.detail,
        )

    _set_refresh_cookie(response, new_refresh_token)
    _set_access_cookie(response, access_token)

    return RefreshResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Logout — delete the current session."""
    refresh_token_cookie = request.cookies.get("refresh_token")
    if refresh_token_cookie:
        auth_service = AuthService(db)
        await auth_service.logout(refresh_token_cookie)

    _clear_refresh_cookie(response)
    _clear_access_cookie(response)
    return MessageResponse(message="Logged out successfully.")


@router.post("/logout-all", response_model=MessageResponse)
async def logout_all(
    response: Response,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Logout from all devices — delete all sessions."""
    auth_service = AuthService(db)
    await auth_service.logout_all(user.id)
    _clear_refresh_cookie(response)
    _clear_access_cookie(response)
    return MessageResponse(message="Logged out from all devices.")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_user)):
    """Get the currently authenticated user."""
    return _user_to_response(user)


@router.post("/verify-email", response_model=MessageResponse)
async def verify_email(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify email using verification token."""
    auth_service = AuthService(db)
    await auth_service.verify_email(token)
    return MessageResponse(message="Email verified successfully.")


@router.post("/resend-verification", response_model=MessageResponse)
async def resend_verification(
    data: ForgotPasswordRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Resend email verification token."""
    auth_service = AuthService(db)
    ip_address = request.client.host if request.client else None
    await auth_service.request_email_verification(data.email, ip_address=ip_address)
    return MessageResponse(
        message="Verification email sent if the account exists and is not verified."
    )


@router.post("/forgot-password", response_model=MessageResponse)
async def forgot_password(
    data: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Send a password reset link to the user's email."""
    auth_service = AuthService(db)
    await auth_service.request_password_reset(data.email)
    return MessageResponse(message="If the email exists, a reset link has been sent.")


@router.post("/verify-reset-token", response_model=MessageResponse)
async def verify_reset_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Verify password reset token validity."""
    auth_service = AuthService(db)
    await auth_service.verify_password_reset_token(token)
    return MessageResponse(message="Token is valid.")


@router.post("/reset-password", response_model=MessageResponse)
async def reset_password(
    data: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    """Reset password using reset token."""
    auth_service = AuthService(db)
    await auth_service.reset_password(data.token, data.new_password)
    return MessageResponse(message="Password reset successfully.")


@router.get("/sessions", response_model=list[SessionResponse])
async def get_sessions(
    request: Request,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all active sessions for the current user."""
    refresh_token_cookie = request.cookies.get("refresh_token")
    current_hash = None
    if refresh_token_cookie:
        current_hash = hashlib.sha256(refresh_token_cookie.encode()).hexdigest()

    auth_service = AuthService(db)
    sessions = await auth_service.session_service.get_active_sessions(user.id)
    return [
        SessionResponse(
            id=str(s.id),
            device_name=s.device_name,
            ip_address=s.ip_address,
            user_agent=s.user_agent,
            last_used_at=s.last_used_at.isoformat() if s.last_used_at else "",
            created_at=s.created_at.isoformat() if s.created_at else "",
            expires_at=s.expires_at.isoformat() if s.expires_at else "",
            is_current=(s.token_hash == current_hash) if current_hash else False,
        )
        for s in sessions
    ]


@router.delete("/sessions/{session_id}", response_model=MessageResponse)
async def revoke_session(
    session_id: uuid.UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Revoke a specific session."""
    auth_service = AuthService(db)
    session = await auth_service.session_service.repo.get_by_id(session_id)
    if not session or session.user_id != user.id:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Session not found.",
        )
    await auth_service.session_service.revoke_session(session_id)
    await db.commit()
    return MessageResponse(message="Session revoked successfully.")


@router.post("/change-password", response_model=MessageResponse)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Change the user's password."""
    from datetime import UTC, datetime

    from app.core.security import hash_password, validate_password, verify_password

    # 1. Verify current password
    if not user.password_hash or not verify_password(body.current_password, user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST, detail="Incorrect current password."
        )

    # 2. Validate and hash new password
    try:
        validate_password(body.new_password)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    user.password_hash = hash_password(body.new_password)
    user.updated_at = datetime.now(UTC).replace(tzinfo=None)

    # 3. Log out of all other devices/sessions for safety
    auth_service = AuthService(db)
    await auth_service.logout_all(user.id)

    await db.commit()
    return MessageResponse(message="Password changed successfully.")

"""Auth API endpoints: register, login, logout, refresh, me."""

from fastapi import APIRouter, Depends, HTTPException, Request, Response, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import require_user
from app.models.models import User
from app.schemas.auth import (
    AuthResponse,
    LoginRequest,
    MessageResponse,
    RefreshResponse,
    RegisterRequest,
    UserResponse,
)
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
    )


def _clear_refresh_cookie(response: Response) -> None:
    """Clear the refresh token cookie."""
    response.delete_cookie(key="refresh_token", path="/")


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
    try:
        user, access_token, refresh_token = await auth_service.register(
            name=body.name, email=body.email, password=body.password
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(e))

    # Create session record
    await auth_service.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    _set_refresh_cookie(response, refresh_token)

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
    try:
        user, access_token, refresh_token = await auth_service.login(
            email=body.email, password=body.password
        )
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials.",
        )

    await auth_service.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    _set_refresh_cookie(response, refresh_token)

    return AuthResponse(
        access_token=access_token,
        user=_user_to_response(user),
    )


@router.post("/refresh", response_model=RefreshResponse)
async def refresh_token(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Refresh the access token using the refresh token cookie."""
    refresh_token = request.cookies.get("refresh_token")
    if not refresh_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="No refresh token.",
        )

    auth_service = AuthService(db)
    try:
        access_token, user = await auth_service.refresh_access_token(refresh_token)
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
        )

    return RefreshResponse(access_token=access_token)


@router.post("/logout", response_model=MessageResponse)
async def logout(
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Logout — delete the current session."""
    refresh_token = request.cookies.get("refresh_token")
    if refresh_token:
        auth_service = AuthService(db)
        await auth_service.logout(refresh_token)

    _clear_refresh_cookie(response)
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
    return MessageResponse(message="Logged out from all devices.")


@router.get("/me", response_model=UserResponse)
async def get_me(user: User = Depends(require_user)):
    """Get the currently authenticated user."""
    return _user_to_response(user)

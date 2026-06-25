"""Google OAuth routes — handles redirect to Google and callback."""

import uuid
from datetime import UTC, datetime
from urllib.parse import urlencode

from authlib.integrations.httpx_client import AsyncOAuth2Client
from fastapi import APIRouter, Depends, HTTPException, Request, Response
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.auth import _set_access_cookie, _set_refresh_cookie
from app.core.config import settings
from app.core.database import get_db
from app.core.security import create_access_token, create_refresh_token
from app.models.models import OAuthAccount, User, UserPreference
from app.services.auth_service import AuthService

router = APIRouter()

GOOGLE_AUTHORIZE_URL = "https://accounts.google.com/o/oauth2/v2/auth"
GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"
GOOGLE_USERINFO_URL = "https://www.googleapis.com/oauth2/v3/userinfo"


def _build_oauth_client() -> AsyncOAuth2Client:
    return AsyncOAuth2Client(
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        redirect_uri=settings.GOOGLE_REDIRECT_URI,
    )


@router.get("/google")
async def google_login():
    """Redirect user to Google OAuth consent screen."""
    if not settings.GOOGLE_CLIENT_ID:
        raise HTTPException(
            status_code=501,
            detail="Google OAuth not configured.",
        )

    params = {
        "client_id": settings.GOOGLE_CLIENT_ID,
        "redirect_uri": settings.GOOGLE_REDIRECT_URI,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
    }
    url = f"{GOOGLE_AUTHORIZE_URL}?{urlencode(params)}"

    from fastapi.responses import RedirectResponse

    return RedirectResponse(url=url)


@router.get("/google/callback")
async def google_callback(
    code: str,
    request: Request,
    response: Response,
    db: AsyncSession = Depends(get_db),
):
    """Handle Google OAuth callback — exchange code for tokens and create/login user."""
    client = _build_oauth_client()

    # Exchange authorization code for tokens
    try:
        token_data = await client.fetch_token(
            GOOGLE_TOKEN_URL,
            code=code,
            grant_type="authorization_code",
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Token exchange failed: {e}")

    # Fetch user info from Google
    client.token = token_data
    resp = await client.get(GOOGLE_USERINFO_URL)
    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail="Failed to fetch user info from Google.")

    userinfo = resp.json()
    google_id = userinfo.get("sub")
    email = userinfo.get("email")
    name = userinfo.get("name")
    picture = userinfo.get("picture")

    if not email:
        raise HTTPException(status_code=400, detail="Email not provided by Google.")

    # Check if user already exists via OAuth account
    oauth_stmt = select(OAuthAccount).where(
        OAuthAccount.provider == "google",
        OAuthAccount.provider_account_id == google_id,
    )
    oauth_res = await db.execute(oauth_stmt)
    oauth_account = oauth_res.scalar_one_or_none()

    user: User | None = None
    if oauth_account:
        # Existing OAuth user — login
        user_stmt = select(User).where(User.id == oauth_account.user_id, User.status == "active")
        user_res = await db.execute(user_stmt)
        user = user_res.scalar_one_or_none()
        if not user:
            raise HTTPException(status_code=403, detail="Account deactivated.")
    else:
        # Check if user exists by email (registered via email/password)
        email_stmt = select(User).where(User.email == email)
        email_res = await db.execute(email_stmt)
        user = email_res.scalar_one_or_none()

        if not user:
            # Create new user
            user = User(
                id=uuid.uuid4(),
                email=email,
                name=name,
                image_url=picture,
                email_verified=True,
                role="user",
                subscription_plan="free",
                status="active",
                created_at=datetime.now(UTC).replace(tzinfo=None),
                updated_at=datetime.now(UTC).replace(tzinfo=None),
            )
            db.add(user)

            # Default preferences
            db.add(
                UserPreference(
                    id=uuid.uuid4(),
                    user_id=user.id,
                    preferred_summary_type="short",
                    theme="system",
                    language="en",
                )
            )
            await db.flush()

        # Link OAuth account
        db.add(
            OAuthAccount(
                id=uuid.uuid4(),
                user_id=user.id,
                provider="google",
                provider_account_id=google_id,
                access_token=token_data.get("access_token"),
                refresh_token=token_data.get("refresh_token"),
            )
        )
        await db.flush()

    # Generate tokens
    access_token = create_access_token({"sub": str(user.id)})
    refresh_token = create_refresh_token({"sub": str(user.id)})

    # Create session
    auth_service = AuthService(db)
    await auth_service.session_service.create_session(
        user_id=user.id,
        refresh_token=refresh_token,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )

    # Redirect to frontend with access token
    frontend_url = settings.CORS_ORIGINS[0] if settings.CORS_ORIGINS else "http://localhost:3000"
    redirect_url = f"{frontend_url}/auth/callback?access_token={access_token}"

    from fastapi.responses import RedirectResponse

    redirect_response = RedirectResponse(url=redirect_url)

    _set_refresh_cookie(redirect_response, refresh_token)
    _set_access_cookie(redirect_response, access_token)

    return redirect_response

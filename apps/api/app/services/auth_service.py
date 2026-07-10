import hashlib
import logging
import secrets
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    validate_password,
    verify_password,
)
from app.exceptions.auth import (
    AccountLockedException,
    AuthException,
    EmailAlreadyVerifiedException,
    EmailNotVerifiedException,
    InvalidCredentialsException,
    InvalidRefreshTokenException,
    SessionExpiredException,
    UserAlreadyExistsException,
)
from app.models.models import UserPreference
from app.models.user import User
from app.repositories.user_repository import UserRepository
from app.services.cache_service import cache_service
from app.services.email_service import EmailService
from app.services.session_service import SessionService

logger = logging.getLogger(__name__)


class AuthService:
    """Handles user authentication workflows and security constraints."""

    def __init__(self, db: AsyncSession):
        self.db = db
        self.user_repo = UserRepository(db)
        self.session_service = SessionService(db)
        self.email_service = EmailService()

    async def register(
        self,
        name: str,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Register a new user, create default preferences, and issue tokens.

        Flow:
        1. Check email uniqueness
        2. Validate password
        3. Hash password
        4. Create user
        5. Create default preferences
        6. Commit transaction
        7. Generate tokens
        8. Create session
        9. Return tokens
        """
        # 1. Check email uniqueness
        existing_user = await self.user_repo.get_by_email(email)
        if existing_user:
            raise UserAlreadyExistsException()

        # 2. Validate password
        validate_password(password)

        # 3. Hash password
        password_hash = hash_password(password)

        now = datetime.now(UTC).replace(tzinfo=None)

        raw_verification_token = secrets.token_urlsafe(32)
        hashed_verification_token = hashlib.sha256(raw_verification_token.encode()).hexdigest()

        # 4. Create user
        user = User(
            id=uuid.uuid4(),
            email=email,
            name=name,
            password_hash=password_hash,
            email_verified=False,
            email_verification_token=hashed_verification_token,
            email_verification_expiry=now + timedelta(hours=24),
            role="user",
            subscription_plan="free",
            status="active",
            created_at=now,
            updated_at=now,
        )
        await self.user_repo.create(user)

        # 5. Create default preferences
        prefs = UserPreference(
            id=uuid.uuid4(),
            user_id=user.id,
            preferred_summary_type="short",
            theme="system",
            language="en",
            created_at=now,
            updated_at=now,
        )
        self.db.add(prefs)

        # 6. Commit transaction
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        # 7. Generate tokens
        access_token = create_access_token(
            {"sub": str(user.id), "email": user.email, "role": user.role}
        )
        refresh_token = create_refresh_token({"sub": str(user.id)})

        # 8. Create session
        await self.session_service.create_session(
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        # Send verification email asynchronously / mock log
        await self.email_service.send_verification_email(user, raw_verification_token)

        # 9. Return tokens
        return user, access_token, refresh_token

    async def login(
        self,
        email: str,
        password: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[User, str, str]:
        """Authenticate active user by email & password with lockout and verification checks.

        Flow:
        1. Find active user
        2. Verify password
        3. Verify account not locked
        4. Verify email confirmed
        5. Reset failed attempts on success
        6. Update last_login_at
        7. Create access token
        8. Create refresh token
        9. Create session
        10. Commit transaction
        """
        # 1. Find active user
        user = await self.user_repo.get_by_email(email)
        now = datetime.now(UTC).replace(tzinfo=None)

        if not user:
            # Timing attack mitigation: run password verification on dummy hash
            verify_password(
                password,
                "$argon2id$v=19$m=65536,t=3,p=4$7f0fI8Q4p/R+b80ZQ8jZew$KdrOSa66x7LTcC5eNU02LBNKB5iNDk+tHxYsrNPM0JI",
            )
            raise InvalidCredentialsException()

        # 3. Verify account not locked
        if user.locked_until and user.locked_until > now:
            raise AccountLockedException(
                f"Account is temporarily locked. Locked until {user.locked_until.isoformat()}."
            )

        # 2. Verify password
        if not user.password_hash or not verify_password(password, user.password_hash):
            # Increment failed login attempts
            user.failed_login_attempts = (user.failed_login_attempts or 0) + 1
            if user.failed_login_attempts >= 5:
                user.locked_until = now + timedelta(minutes=15)
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            raise InvalidCredentialsException()

        # 4. Verify email confirmed
        if not user.email_verified:
            raise EmailNotVerifiedException()

        if user.status != "active":
            raise InvalidCredentialsException("Account is not active.")

        # 5. Reset failed attempts on success
        user.failed_login_attempts = 0
        user.locked_until = None

        # 6. Update last_login_at
        user.last_login_at = now
        user.updated_at = now

        # 7. Create access token
        access_token = create_access_token(
            {"sub": str(user.id), "email": user.email, "role": user.role}
        )

        # 8. Create refresh token
        refresh_token = create_refresh_token({"sub": str(user.id)})

        # 9. Create session
        await self.session_service.create_session(
            user_id=user.id,
            refresh_token=refresh_token,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 10. Commit transaction
        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return user, access_token, refresh_token

    async def rotate_refresh_token(
        self,
        refresh_token: str,
        ip_address: str | None = None,
        user_agent: str | None = None,
    ) -> tuple[str, str, User]:
        """Verify, rotate refresh token, and generate new token pair.

        Old refresh tokens must become unusable. Revoke all sessions on reuse detection.
        """
        payload = decode_token(refresh_token)
        if not payload or payload.get("type") != "refresh":
            raise InvalidRefreshTokenException()

        user_id_str = payload.get("sub")
        if not user_id_str:
            raise InvalidRefreshTokenException()

        token_hash = self.session_service.hash_token(refresh_token)

        # Verify session
        session = await self.session_service.repo.get_by_token_hash(token_hash)
        if not session:
            # Token reuse/theft detection: invalidate all sessions of the user
            try:
                user_id = uuid.UUID(user_id_str)
                await self.session_service.logout_all(user_id)
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            raise InvalidRefreshTokenException(
                "Refresh token reused or session invalid. Revoking all sessions."
            )

        now = datetime.now(UTC).replace(tzinfo=None)
        if session.expires_at < now:
            await self.session_service.repo.delete(session)
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            raise SessionExpiredException()

        user = session.user
        if not user or user.status != "active":
            await self.session_service.repo.delete(session)
            try:
                await self.db.commit()
            except Exception:
                await self.db.rollback()
            raise InvalidCredentialsException("User inactive or not found.")

        # Delete session A
        await self.session_service.repo.delete(session)

        # Generate new access token
        access_token = create_access_token(
            {"sub": str(user.id), "email": user.email, "role": user.role}
        )

        # Generate refresh token B
        new_refresh_token = create_refresh_token({"sub": str(user.id)})

        # Create session B
        await self.session_service.create_session(
            user_id=user.id,
            refresh_token=new_refresh_token,
            ip_address=ip_address or session.ip_address,
            user_agent=user_agent or session.user_agent,
        )

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return access_token, new_refresh_token, user

    async def logout(self, refresh_token: str) -> None:
        """Logout current device by deleting only its session."""
        try:
            await self.session_service.logout(refresh_token)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def logout_all(self, user_id: uuid.UUID) -> None:
        """Logout all devices belonging to the user."""
        try:
            await self.session_service.logout_all(user_id)
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

    async def request_email_verification(self, email: str, ip_address: str | None = None) -> None:
        """Generate email verification token and send email."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            # Silent return to prevent user enumeration
            return

        if user.email_verified:
            raise EmailAlreadyVerifiedException()

        # Redis rate-limiting (fail open if Redis is down)
        email_key = f"rate_limit:resend:{email}"
        try:
            if await cache_service.get_raw(email_key):
                raise AuthException(
                    "Please wait at least 60 seconds before requesting another verification email."
                )

            if ip_address:
                ip_key = f"rate_limit:resend:ip:{ip_address}"
                ip_count_str = await cache_service.get_raw(ip_key)
                if ip_count_str and int(ip_count_str) >= 5:
                    raise AuthException(
                        "Too many verification requests from this IP. Please try again later."
                    )
        except AuthException:
            raise
        except Exception as e:
            logger.warning("Resend email rate limit check failed (fail open): %s", e)

        now = datetime.now(UTC).replace(tzinfo=None)
        raw_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

        user.email_verification_token = hashed_token
        user.email_verification_expiry = now + timedelta(hours=24)
        user.updated_at = now

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        # Save rate limits in Redis
        # Save rate limits in Redis
        try:
            await cache_service.set_raw(email_key, "1", ttl=60)
            if ip_address:
                ip_key = f"rate_limit:resend:ip:{ip_address}"
                await cache_service.incr(ip_key, ttl=3600)  # Increment and set 1h TTL
        except Exception as e:
            logger.warning("Failed to save resend email rate limits in Redis: %s", e)

        await self.email_service.send_verification_email(user, raw_token)

    async def verify_email(self, token: str) -> User:
        """Verify email using verification token."""
        user = await self.user_repo.get_by_verification_token(token)
        if not user:
            raise InvalidCredentialsException("Invalid or expired verification token.")

        now = datetime.now(UTC).replace(tzinfo=None)
        if user.email_verification_expiry and user.email_verification_expiry < now:
            raise InvalidCredentialsException("Verification token has expired.")

        user.email_verified = True
        user.email_verification_token = None
        user.email_verification_expiry = None
        user.updated_at = now

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        return user

    async def request_password_reset(self, email: str) -> None:
        """Generate password reset token and send email."""
        user = await self.user_repo.get_by_email(email)
        if not user:
            return

        now = datetime.now(UTC).replace(tzinfo=None)
        raw_token = secrets.token_urlsafe(32)
        hashed_token = hashlib.sha256(raw_token.encode()).hexdigest()

        user.password_reset_token = hashed_token
        user.password_reset_expiry = now + timedelta(hours=1)
        user.updated_at = now

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

        await self.email_service.send_password_reset_email(user, raw_token)

    async def verify_password_reset_token(self, token: str) -> User:
        """Verify password reset token and return User if valid."""
        user = await self.user_repo.get_by_password_reset_token(token)
        if not user:
            raise InvalidCredentialsException("Invalid or expired password reset token.")

        now = datetime.now(UTC).replace(tzinfo=None)
        if user.password_reset_expiry and user.password_reset_expiry < now:
            raise InvalidCredentialsException("Password reset token has expired.")

        return user

    async def reset_password(self, token: str, new_password: str) -> None:
        """Verify password reset token, update password, and invalidate all active sessions."""
        user = await self.verify_password_reset_token(token)
        validate_password(new_password)

        now = datetime.now(UTC).replace(tzinfo=None)
        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expiry = None
        user.updated_at = now

        # Invalidate old sessions after password change
        await self.session_service.logout_all(user.id)

        try:
            await self.db.commit()
        except Exception:
            await self.db.rollback()
            raise

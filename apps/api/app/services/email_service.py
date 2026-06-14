"""Email service for sending verification and password reset emails."""

import logging

from app.models.user import User

logger = logging.getLogger(__name__)


class EmailService:
    """Mock/Audit-friendly email service for sending authentication links."""

    async def send_verification_email(self, user: User, token: str) -> None:
        """Log secure token for verifying user email."""
        logger.info(
            "AUDIT: Verification email requested for user %s (%s). Token: %s",
            user.id,
            user.email,
            token,
        )

    async def send_password_reset_email(self, user: User, token: str) -> None:
        """Log secure token for resetting user password."""
        logger.info(
            "AUDIT: Password reset email requested for user %s (%s). Token: %s",
            user.id,
            user.email,
            token,
        )

import logging
import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.models import (
    Category,
    DigestSubscription,
    Notification,
    Story,
    UserCategory,
    UserPreference,
)
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)


class DigestDeliveryService:
    def __init__(self):
        self.email_service = EmailService()

    async def compile_and_deliver_digests(self, db: AsyncSession, frequency: str) -> int:
        """Compile and deliver news digests for the given frequency/edition."""
        logger.info("Digest delivery: Starting delivery for frequency '%s'.", frequency)

        # 1. Fetch all active subscriptions for this frequency
        stmt = (
            select(DigestSubscription)
            .where(DigestSubscription.frequency == frequency, DigestSubscription.enabled)
            .options(selectinload(DigestSubscription.user))
        )
        result = await db.execute(stmt)
        subscriptions = result.scalars().all()

        if not subscriptions:
            logger.info("Digest delivery: No active subscriptions found for '%s'.", frequency)
            return 0

        # Group subscriptions by user to avoid duplicate compilation for different channels (e.g. email + in_app)
        user_subscriptions: dict[uuid.UUID, dict[str, Any]] = {}
        for sub in subscriptions:
            if not sub.user:
                continue
            if sub.user_id not in user_subscriptions:
                user_subscriptions[sub.user_id] = {"user": sub.user, "channels": []}
            user_subscriptions[sub.user_id]["channels"].append(sub.delivery_channel)

        processed_count = 0
        EDITIONS_MAP = {
            "morning": "Morning Digest",
            "midday": "Midday Brief",
            "evening": "Evening Wrap",
            "weekly": "Weekly Summary",
        }
        edition_title = EDITIONS_MAP.get(frequency, f"{frequency.capitalize()} Digest")

        for user_id, udata in user_subscriptions.items():
            user = udata["user"]
            channels = udata["channels"]

            try:
                # 2. Get user preferences for story count
                pref_stmt = select(UserPreference).where(UserPreference.user_id == user_id)
                pref_result = await db.execute(pref_stmt)
                prefs = pref_result.scalar_one_or_none()

                story_count = 5
                if prefs and prefs.digest_settings:
                    story_count = prefs.digest_settings.get("story_count", 5)

                # 3. Get user preferred categories
                cat_query = (
                    select(Category.id).join(UserCategory).where(UserCategory.user_id == user_id)
                )
                cat_result = await db.execute(cat_query)
                category_ids = [row[0] for row in cat_result.all()]

                # 4. Fetch stories matching categories, ordered by created_at desc
                story_query = select(Story).order_by(Story.created_at.desc()).limit(story_count)
                if category_ids:
                    story_query = story_query.where(Story.category_id.in_(category_ids))

                s_result = await db.execute(story_query)
                stories = s_result.scalars().all()

                # Fallback to general latest stories if none matching category preferences
                if not stories:
                    fallback_query = (
                        select(Story).order_by(Story.created_at.desc()).limit(story_count)
                    )
                    f_result = await db.execute(fallback_query)
                    stories = f_result.scalars().all()

                if not stories:
                    logger.warning(
                        "Digest delivery: No stories available to compile digest for user %s.",
                        user.email,
                    )
                    continue

                # Format stories to match frontend expected payload
                stories_payload = [
                    {
                        "story_id": str(s.id),
                        "headline": s.headline,
                        "one_line_summary": s.one_line_summary,
                        "short_summary": s.short_summary,
                        "category_id": str(s.category_id) if s.category_id else None,
                    }
                    for s in stories
                ]

                # 5. Deliver via each channel
                for channel in channels:
                    if channel == "email":
                        await self.email_service.send_digest_email(
                            user, edition_title, stories_payload
                        )
                        logger.info(
                            "Digest delivery: Sent email digest to %s for edition '%s'.",
                            user.email,
                            edition_title,
                        )
                    elif channel == "in_app":
                        headline_preview = stories[0].headline if stories else ""
                        body_text = f"Here is your latest briefing featuring: {headline_preview}"
                        notification = Notification(
                            id=uuid.uuid4(),
                            user_id=user_id,
                            title=f"Your {edition_title} is ready!",
                            body=body_text,
                            notification_type="digest",
                            is_read=False,
                        )
                        db.add(notification)
                        logger.info(
                            "Digest delivery: Created in-app notification for %s for edition '%s'.",
                            user.email,
                            edition_title,
                        )

                processed_count += 1
            except Exception as e:
                logger.error(
                    "Digest delivery: Failed to compile or deliver digest for user %s: %s",
                    user.email,
                    e,
                )

        await db.commit()
        return processed_count


digest_delivery_service = DigestDeliveryService()

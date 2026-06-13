"""User API endpoints: profile, preferences, onboarding."""

import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import get_db
from app.core.deps import require_user
from app.models.models import (
    Category,
    User,
    UserCategory,
    UserLocation,
    UserPreference,
)
from app.schemas.auth import MessageResponse, UserResponse
from app.schemas.user import (
    DigestSubscriptionResponse,
    DigestSubscriptionUpdate,
    NotificationResponse,
    OnboardingRequest,
    ProfileUpdateRequest,
    UserPreferencesResponse,
    UserPreferencesUpdate,
)

router = APIRouter()


@router.get("/profile", response_model=UserResponse)
async def get_profile(user: User = Depends(require_user)):
    """Get the current user's profile."""
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


@router.patch("/profile", response_model=UserResponse)
async def update_profile(
    body: ProfileUpdateRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user profile (name, image only). Role/plan changes require admin."""
    if body.name is not None:
        user.name = body.name
    if body.image_url is not None:
        user.image_url = body.image_url
    # NOTE: subscription_plan and role are intentionally NOT updatable here.
    # Use the admin endpoint PATCH /admin/users/{user_id}/role instead.
    user.updated_at = datetime.now(UTC)
    await db.flush()

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


@router.get("/preferences", response_model=UserPreferencesResponse)
async def get_preferences(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the current user's preferences."""
    # Fetch preferences
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    prefs = result.scalar_one_or_none()

    # Fetch user categories
    result = await db.execute(
        select(Category.slug)
        .join(UserCategory, UserCategory.category_id == Category.id)
        .where(UserCategory.user_id == user.id)
    )
    categories = [row[0] for row in result.all()]

    # Fetch user locations
    result = await db.execute(select(UserLocation).where(UserLocation.user_id == user.id))
    locations = result.scalars().all()
    countries = list({loc.country_code for loc in locations if loc.country_code})
    cities = list({loc.city_name for loc in locations if loc.city_name})

    return UserPreferencesResponse(
        preferred_summary_type=prefs.preferred_summary_type if prefs else "short",
        theme=prefs.theme if prefs else "system",
        language=prefs.language if prefs else "en",
        categories=categories,
        countries=countries,
        cities=cities,
    )


@router.patch("/preferences", response_model=MessageResponse)
async def update_preferences(
    body: UserPreferencesUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update user preferences."""
    # Update or create preferences
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserPreference(id=uuid.uuid4(), user_id=user.id)
        db.add(prefs)

    if body.preferred_summary_type is not None:
        prefs.preferred_summary_type = body.preferred_summary_type
    if body.theme is not None:
        prefs.theme = body.theme
    if body.language is not None:
        prefs.language = body.language
    prefs.updated_at = datetime.now(UTC)

    # Update categories if provided
    if body.categories is not None:
        await db.execute(delete(UserCategory).where(UserCategory.user_id == user.id))
        for slug in body.categories:
            result = await db.execute(select(Category).where(Category.slug == slug))
            cat = result.scalar_one_or_none()
            if cat:
                db.add(UserCategory(user_id=user.id, category_id=cat.id))

    # Update locations if provided
    if body.countries is not None or body.cities is not None:
        await db.execute(delete(UserLocation).where(UserLocation.user_id == user.id))
        if body.countries:
            for country in body.countries:
                db.add(
                    UserLocation(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        country_code=country,
                    )
                )
        if body.cities:
            for city in body.cities:
                db.add(
                    UserLocation(
                        id=uuid.uuid4(),
                        user_id=user.id,
                        city_name=city,
                    )
                )

    await db.flush()
    return MessageResponse(message="Preferences updated.")


@router.post("/onboarding", response_model=MessageResponse)
async def complete_onboarding(
    body: OnboardingRequest,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Save onboarding selections (categories, locations, summary type)."""
    # Save preferences
    result = await db.execute(select(UserPreference).where(UserPreference.user_id == user.id))
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserPreference(id=uuid.uuid4(), user_id=user.id)
        db.add(prefs)

    prefs.preferred_summary_type = body.preferred_summary_type
    prefs.updated_at = datetime.now(UTC)

    # Save categories
    await db.execute(delete(UserCategory).where(UserCategory.user_id == user.id))
    for slug in body.categories:
        result = await db.execute(select(Category).where(Category.slug == slug))
        cat = result.scalar_one_or_none()
        if cat:
            db.add(UserCategory(user_id=user.id, category_id=cat.id))

    # Save locations
    await db.execute(delete(UserLocation).where(UserLocation.user_id == user.id))
    for country in body.countries:
        db.add(UserLocation(id=uuid.uuid4(), user_id=user.id, country_code=country))
    for city in body.cities:
        db.add(UserLocation(id=uuid.uuid4(), user_id=user.id, city_name=city))

    await db.flush()
    return MessageResponse(message="Onboarding complete.")


@router.delete("/account", response_model=MessageResponse)
async def delete_account(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the user's account (danger zone)."""
    user.status = "deleted"
    user.updated_at = datetime.now(UTC)
    await db.flush()
    return MessageResponse(message="Account deleted.")


@router.get("/notifications", response_model=list[NotificationResponse])
async def get_notifications(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get all notifications for the current user."""
    from app.models.models import Notification

    result = await db.execute(
        select(Notification)
        .where(Notification.user_id == user.id)
        .order_by(Notification.created_at.desc())
    )
    notifications = result.scalars().all()
    return [
        NotificationResponse(
            id=str(n.id),
            title=n.title,
            body=n.body,
            notification_type=n.notification_type,
            is_read=n.is_read,
            created_at=n.created_at.isoformat() if n.created_at else "",
        )
        for n in notifications
    ]


@router.patch("/notifications/{notification_id}/read", response_model=MessageResponse)
async def mark_notification_as_read(
    notification_id: uuid.UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Mark a notification as read."""
    from app.models.models import Notification

    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    notification.is_read = True
    await db.flush()
    return MessageResponse(message="Notification marked as read.")


@router.delete("/notifications/{notification_id}", response_model=MessageResponse)
async def delete_notification(
    notification_id: uuid.UUID,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Delete a notification."""
    from app.models.models import Notification

    result = await db.execute(
        select(Notification).where(
            Notification.id == notification_id, Notification.user_id == user.id
        )
    )
    notification = result.scalar_one_or_none()
    if not notification:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Notification not found")
    await db.delete(notification)
    await db.flush()
    return MessageResponse(message="Notification deleted.")


@router.get("/digests", response_model=list[DigestSubscriptionResponse])
async def get_digest_subscriptions(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get user digest subscriptions."""
    from app.models.models import DigestSubscription

    result = await db.execute(
        select(DigestSubscription).where(DigestSubscription.user_id == user.id)
    )
    subs = result.scalars().all()
    return subs


@router.patch("/digests", response_model=MessageResponse)
async def update_digest_subscriptions(
    body: DigestSubscriptionUpdate,
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Update or create digest subscriptions."""
    from app.models.models import DigestSubscription

    result = await db.execute(
        select(DigestSubscription).where(
            DigestSubscription.user_id == user.id,
            DigestSubscription.frequency == body.frequency,
            DigestSubscription.delivery_channel == body.delivery_channel,
        )
    )
    sub = result.scalar_one_or_none()
    if not sub:
        sub = DigestSubscription(
            id=uuid.uuid4(),
            user_id=user.id,
            frequency=body.frequency,
            delivery_channel=body.delivery_channel,
        )
        db.add(sub)
    sub.enabled = body.enabled
    await db.flush()
    return MessageResponse(message="Digest subscription updated.")


@router.get("/digests/latest")
async def get_latest_digest(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Get the latest AI summary digest for user's preferred categories."""
    from app.models.models import Category, Story, UserCategory

    # Get user preferred categories
    cat_query = select(Category.id).join(UserCategory).where(UserCategory.user_id == user.id)
    cat_result = await db.execute(cat_query)
    category_ids = [row[0] for row in cat_result.all()]

    # Query stories in those categories ordered by created_at (not Story.created_at which was missing)
    story_query = select(Story).order_by(Story.created_at.desc()).limit(5)
    if category_ids:
        story_query = story_query.where(Story.category_id.in_(category_ids))

    result = await db.execute(story_query)
    stories = result.scalars().all()

    # Fallback to most recent stories if no category match
    if not stories:
        fallback_result = await db.execute(
            select(Story).order_by(Story.created_at.desc()).limit(5)
        )
        stories = fallback_result.scalars().all()

    digest_items = [
        {
            "story_id": str(s.id),
            "headline": s.headline,
            "one_line_summary": s.one_line_summary,
            "short_summary": s.short_summary,
            "category_id": str(s.category_id) if s.category_id else None,
            "created_at": s.created_at.isoformat() if s.created_at else "",
        }
        for s in stories
    ]

    from datetime import UTC, datetime

    return {
        "digest_type": "Daily Briefing",
        "generated_at": datetime.now(UTC).isoformat(),
        "title": "Your NewsIQ Intelligence Briefing",
        "items": digest_items,
    }

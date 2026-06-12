"""User API endpoints: profile, preferences, onboarding."""

import uuid
from datetime import datetime, timezone

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
    """Update user profile (name, image)."""
    if body.name is not None:
        user.name = body.name
    if body.image_url is not None:
        user.image_url = body.image_url
    user.updated_at = datetime.now(timezone.utc)
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
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()

    # Fetch user categories
    result = await db.execute(
        select(Category.slug)
        .join(UserCategory, UserCategory.category_id == Category.id)
        .where(UserCategory.user_id == user.id)
    )
    categories = [row[0] for row in result.all()]

    # Fetch user locations
    result = await db.execute(
        select(UserLocation).where(UserLocation.user_id == user.id)
    )
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
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
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
    prefs.updated_at = datetime.now(timezone.utc)

    # Update categories if provided
    if body.categories is not None:
        await db.execute(
            delete(UserCategory).where(UserCategory.user_id == user.id)
        )
        for slug in body.categories:
            result = await db.execute(
                select(Category).where(Category.slug == slug)
            )
            cat = result.scalar_one_or_none()
            if cat:
                db.add(UserCategory(user_id=user.id, category_id=cat.id))

    # Update locations if provided
    if body.countries is not None or body.cities is not None:
        await db.execute(
            delete(UserLocation).where(UserLocation.user_id == user.id)
        )
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
    result = await db.execute(
        select(UserPreference).where(UserPreference.user_id == user.id)
    )
    prefs = result.scalar_one_or_none()

    if not prefs:
        prefs = UserPreference(id=uuid.uuid4(), user_id=user.id)
        db.add(prefs)

    prefs.preferred_summary_type = body.preferred_summary_type
    prefs.updated_at = datetime.now(timezone.utc)

    # Save categories
    await db.execute(
        delete(UserCategory).where(UserCategory.user_id == user.id)
    )
    for slug in body.categories:
        result = await db.execute(select(Category).where(Category.slug == slug))
        cat = result.scalar_one_or_none()
        if cat:
            db.add(UserCategory(user_id=user.id, category_id=cat.id))

    # Save locations
    await db.execute(
        delete(UserLocation).where(UserLocation.user_id == user.id)
    )
    for country in body.countries:
        db.add(
            UserLocation(id=uuid.uuid4(), user_id=user.id, country_code=country)
        )
    for city in body.cities:
        db.add(
            UserLocation(id=uuid.uuid4(), user_id=user.id, city_name=city)
        )

    await db.flush()
    return MessageResponse(message="Onboarding complete.")


@router.delete("/account", response_model=MessageResponse)
async def delete_account(
    user: User = Depends(require_user),
    db: AsyncSession = Depends(get_db),
):
    """Permanently delete the user's account (danger zone)."""
    user.status = "deleted"
    user.updated_at = datetime.now(timezone.utc)
    await db.flush()
    return MessageResponse(message="Account deleted.")

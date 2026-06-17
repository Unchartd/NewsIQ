"""Pydantic schemas for user profile and preferences."""

import uuid
from pydantic import BaseModel, Field


class UserPreferencesUpdate(BaseModel):
    """Payload for updating user preferences."""

    preferred_summary_type: str | None = Field(None, pattern="^(one_line|short|detailed)$")
    theme: str | None = Field(None, pattern="^(light|dark|system)$")
    language: str | None = None
    categories: list[str] | None = None  # list of category slugs
    countries: list[str] | None = None
    cities: list[str] | None = None
    digest_settings: dict | None = None


class UserPreferencesResponse(BaseModel):
    """User preferences response."""

    preferred_summary_type: str | None
    theme: str | None
    language: str | None
    categories: list[str]
    countries: list[str]
    cities: list[str]
    digest_settings: dict | None = None

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """Payload for updating user profile.

    NOTE: subscription_plan and role are intentionally excluded.
    Use the admin-only PATCH /admin/users/{user_id}/role endpoint instead.
    """

    name: str | None = Field(None, min_length=1, max_length=255)
    image_url: str | None = None


class OnboardingRequest(BaseModel):
    """Onboarding step data — categories, locations, summary preference."""

    categories: list[str] = Field(..., min_length=1)  # at least 1 category required
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    preferred_summary_type: str = Field("short", pattern="^(one_line|short|detailed)$")


class NotificationResponse(BaseModel):
    """Schema for notification response."""

    id: uuid.UUID
    title: str | None
    body: str | None
    notification_type: str | None
    is_read: bool
    created_at: str

    model_config = {"from_attributes": True}


class DigestSubscriptionUpdate(BaseModel):
    """Schema for updating digest subscriptions."""

    frequency: str = Field(..., pattern="^(morning|midday|evening|weekly)$")
    delivery_channel: str | None = Field(default=None, pattern="^(in_app|email|telegram|push)$")
    enabled: bool


class DigestSubscriptionResponse(BaseModel):
    """Schema for digest subscription response."""

    id: uuid.UUID
    frequency: str | None
    delivery_channel: str | None
    enabled: bool

    model_config = {"from_attributes": True}


class DigestSetupRequest(BaseModel):
    """Payload for full digest configuration setup."""

    categories: list[str]
    story_count: int
    prioritize_local: bool
    include_world: bool
    editions: dict[str, bool]
    delivery_times: dict[str, str]
    frequency: str  # daily, weekdays, custom
    custom_days: list[str]
    weekly_wrap: bool
    channels: dict[str, bool]
    email_format: str  # html, text

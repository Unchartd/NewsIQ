"""Pydantic schemas for user profile and preferences."""

from pydantic import BaseModel, Field


class UserPreferencesUpdate(BaseModel):
    """Payload for updating user preferences."""
    preferred_summary_type: str | None = Field(None, pattern="^(one_line|short|detailed)$")
    theme: str | None = Field(None, pattern="^(light|dark|system)$")
    language: str | None = None
    categories: list[str] | None = None  # list of category slugs
    countries: list[str] | None = None
    cities: list[str] | None = None


class UserPreferencesResponse(BaseModel):
    """User preferences response."""
    preferred_summary_type: str | None
    theme: str | None
    language: str | None
    categories: list[str]
    countries: list[str]
    cities: list[str]

    model_config = {"from_attributes": True}


class ProfileUpdateRequest(BaseModel):
    """Payload for updating user profile."""
    name: str | None = Field(None, min_length=1, max_length=255)
    image_url: str | None = None


class OnboardingRequest(BaseModel):
    """Onboarding step data — categories, locations, summary preference."""
    categories: list[str] = Field(..., min_length=1)  # at least 1 category required
    countries: list[str] = Field(default_factory=list)
    cities: list[str] = Field(default_factory=list)
    preferred_summary_type: str = Field("short", pattern="^(one_line|short|detailed)$")

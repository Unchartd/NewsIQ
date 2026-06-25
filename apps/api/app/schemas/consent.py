"""Pydantic schemas for Consent Management Platform (CMP)."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field


class ConsentPreferencesSaveRequest(BaseModel):
    """Payload for saving user/anonymous consent preferences."""

    anonymous_id: str = Field(
        ..., description="Unique client-side generated identifier for anonymous tracking."
    )
    functional: bool = Field(
        False, description="Consent for preference and custom layouts storage."
    )
    analytics: bool = Field(
        False, description="Consent for privacy-focused clickstream and analytics tracking."
    )
    marketing: bool = Field(False, description="Consent for third-party pixel conversion tracking.")
    region: str = Field(..., description="Detected or overridden region of the client.")
    consent_version: str = Field(
        ..., description="Active version tag of the policy being consented to."
    )


class ConsentPreferencesResponse(BaseModel):
    """Response containing cookie preferences status."""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    anonymous_id: str
    essential: bool = True
    functional: bool
    analytics: bool
    marketing: bool
    region: str
    consent_version: str
    accepted_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ConsentAuditLogResponse(BaseModel):
    """Response containing audit log details."""

    id: uuid.UUID
    user_id: uuid.UUID | None = None
    anonymous_id: str
    action: str
    old_value: dict | None = None
    new_value: dict
    timestamp: datetime
    consent_version: str

    model_config = {"from_attributes": True}


class CookieCategoryDefaults(BaseModel):
    """Default cookie category states for a region."""

    essential: bool = True
    functional: bool
    analytics: bool
    marketing: bool


class RegionDetectionResponse(BaseModel):
    """Response for detected client region and default policy rules."""

    region: str = Field(
        ..., description="Code representing the detected region (EU, UK, CA, IN, ROW)."
    )
    ip: str = Field(..., description="Anonymized/truncated client IP address.")
    defaults: CookieCategoryDefaults = Field(
        ..., description="Default cookie enablement settings for this region."
    )
    require_explicit_opt_in: bool = Field(
        ..., description="Whether the region requires active opt-in before tracking."
    )
    support_opt_out: bool = Field(
        ..., description="Whether the region allows opting out of pre-selected tracking."
    )

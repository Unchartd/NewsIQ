"""Pydantic schemas for authentication endpoints."""

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    """User registration payload."""

    name: str = Field(..., min_length=1, max_length=255)
    email: EmailStr
    password: str = Field(..., min_length=8, max_length=128)
    confirm_password: str = Field(..., min_length=8, max_length=128)


class LoginRequest(BaseModel):
    """Email + password login payload."""

    email: EmailStr
    password: str


class ForgotPasswordRequest(BaseModel):
    """Payload for password reset."""

    email: EmailStr


class ResetPasswordRequest(BaseModel):
    """Payload for resetting password with token."""

    token: str
    new_password: str = Field(..., min_length=8, max_length=128)


class AuthResponse(BaseModel):
    """Returned after successful login/register."""

    access_token: str
    token_type: str = "bearer"
    user: "UserResponse"


class RefreshResponse(BaseModel):
    """Returned after token refresh."""

    access_token: str
    token_type: str = "bearer"


class UserResponse(BaseModel):
    """Public user representation."""

    id: str
    email: str
    name: str | None
    image_url: str | None
    role: str
    subscription_plan: str
    status: str
    email_verified: bool
    created_at: str

    model_config = {"from_attributes": True}


class SessionResponse(BaseModel):
    """Session representation for active sessions list."""

    id: str
    device_name: str | None
    ip_address: str | None
    user_agent: str | None
    last_used_at: str
    created_at: str
    expires_at: str

    model_config = {"from_attributes": True}


class MessageResponse(BaseModel):
    """Generic message response."""

    message: str

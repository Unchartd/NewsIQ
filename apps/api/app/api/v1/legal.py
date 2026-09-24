"""Legal, privacy, copyright, abuse and contact requests from the website forms.

These forms used to show "Request submitted successfully. Our legal
department will review within 72 hours" without sending anything: privacy
requests the Privacy Policy promises to honour and copyright notices the Terms
promise to act on were discarded in the browser. Every request now reaches the
monitored inbox (settings.LEGAL_CONTACT_EMAIL) with the requester as Reply-To,
and the form is told the truth when delivery fails.
"""

import logging
import secrets
from typing import Literal

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.core.config import settings
from app.services.email_service import EmailService

logger = logging.getLogger(__name__)

router = APIRouter()


class LegalRequest(BaseModel):
    kind: Literal["privacy", "copyright", "abuse", "contact"]
    email: EmailStr
    details: str = Field(min_length=10, max_length=5000)
    name: str | None = Field(default=None, max_length=200)
    subject: str | None = Field(default=None, max_length=200)
    request_type: str | None = Field(default=None, max_length=50)
    reference_url: str | None = Field(default=None, max_length=1000)
    # Honeypot: hidden in the form, so only bots fill it in.
    website: str | None = Field(default=None, max_length=200)


class LegalRequestReceipt(BaseModel):
    reference: str
    message: str


@router.post("/requests", response_model=LegalRequestReceipt, status_code=status.HTTP_202_ACCEPTED)
async def submit_legal_request(payload: LegalRequest) -> LegalRequestReceipt:
    reference = "NIQ-" + secrets.token_hex(4).upper()
    if payload.website:
        # Answer like a success so the bot learns nothing; deliver nothing.
        logger.info("Legal request %s dropped by honeypot", reference)
        return LegalRequestReceipt(reference=reference, message="Received.")

    try:
        await EmailService().send_legal_request(
            reference=reference,
            kind=payload.kind,
            request_type=payload.request_type,
            requester_email=payload.email,
            name=payload.name,
            subject=payload.subject,
            details=payload.details,
            reference_url=payload.reference_url,
        )
    except Exception:
        logger.exception("Legal request %s (%s) could not be delivered", reference, payload.kind)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Your request could not be sent right now. Please email "
                f"{settings.LEGAL_CONTACT_EMAIL} directly."
            ),
        )

    logger.info("Legal request %s (%s) delivered", reference, payload.kind)
    return LegalRequestReceipt(
        reference=reference,
        message=f"Received. We will reply to {payload.email} (reference {reference}).",
    )

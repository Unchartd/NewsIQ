"""FastAPI endpoints for Consent Management Platform (CMP)."""

import hashlib
from datetime import UTC, datetime

from fastapi import APIRouter, Depends, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.database import get_db
from app.core.deps import get_current_user, require_user
from app.models.consent import ConsentAuditLog, ConsentPreference
from app.models.models import User
from app.schemas.consent import (
    ConsentAuditLogResponse,
    ConsentPreferencesResponse,
    ConsentPreferencesSaveRequest,
    RegionDetectionResponse,
)

router = APIRouter()


def _get_client_ip(request: Request) -> str:
    """Extract real client IP address from proxy headers."""
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        # Get first element of comma-separated list
        return forwarded.split(",")[0].strip()
    return request.headers.get("x-real-ip") or request.client.host or "127.0.0.1"


def _hash_ip(ip: str) -> str:
    """Hash the client IP using SHA-256 with SECRET_KEY salt for GDPR compliance."""
    salted = f"{ip}:{settings.SECRET_KEY}"
    return hashlib.sha256(salted.encode()).hexdigest()


def detect_client_region(request: Request) -> str:
    """Detect visitor's compliance region based on edge proxy headers, query, or overrides."""
    # 1. Query parameter override or header override (primarily for local developer testing)
    override = request.headers.get("x-consent-region-override") or request.query_params.get(
        "region"
    )
    if override:
        val = override.upper()
        if val in ("EU", "UK", "CA", "IN", "ROW"):
            return val
        if val == "GB":
            return "UK"
        if val == "US":
            return "CA"

    # 2. Check standard CDN/Proxy headers (Cloudflare, Vercel, AppEngine)
    edge_country = (
        request.headers.get("cf-ipcountry")
        or request.headers.get("x-vercel-ip-country")
        or request.headers.get("x-appengine-country")
        or request.headers.get("x-country-code")
    )
    if edge_country:
        country = edge_country.upper()
        if country in ("GB", "UK"):
            return "UK"
        if country == "IN":
            return "IN"
        if country in ("US", "USA"):
            # If Vercel region header specifies California
            state = request.headers.get("x-vercel-ip-country-region") or request.headers.get(
                "x-region"
            )
            if state and state.upper() in ("CA", "CALIFORNIA"):
                return "CA"
            # Default US to California CCPA/CPRA rules for safety
            return "CA"

        # EU Member States
        eu_countries = {
            "AT",
            "BE",
            "BG",
            "HR",
            "CY",
            "CZ",
            "DK",
            "EE",
            "FI",
            "FR",
            "DE",
            "GR",
            "HU",
            "IE",
            "IT",
            "LV",
            "LT",
            "LU",
            "MT",
            "NL",
            "PL",
            "PT",
            "RO",
            "SK",
            "SI",
            "ES",
            "SE",
        }
        if country in eu_countries:
            return "EU"

    return "ROW"


def get_region_defaults(region: str) -> dict:
    """Return default cookie preferences and compliance settings for a region."""
    if region in ("EU", "UK", "IN"):
        return {
            "essential": True,
            "functional": False,
            "analytics": False,
            "marketing": False,
            "require_explicit_opt_in": True,
            "support_opt_out": False,
        }
    elif region == "CA":
        return {
            "essential": True,
            "functional": True,
            "analytics": True,
            "marketing": True,
            "require_explicit_opt_in": False,
            "support_opt_out": True,
        }
    else:  # ROW (Rest of World)
        return {
            "essential": True,
            "functional": True,
            "analytics": True,
            "marketing": False,
            "require_explicit_opt_in": False,
            "support_opt_out": False,
        }


@router.get("/region", response_model=RegionDetectionResponse)
async def get_region(request: Request):
    """Detect current region and return compliance configuration and default states."""
    region = detect_client_region(request)
    ip = _get_client_ip(request)

    # Anonymize IP shown to client (e.g. 192.168.1.5 -> 192.168.1.xxx)
    ip_parts = ip.split(".")
    if len(ip_parts) == 4:
        anonymized_ip = f"{ip_parts[0]}.{ip_parts[1]}.{ip_parts[2]}.xxx"
    else:
        anonymized_ip = "xxx.xxx.xxx.xxx"

    rules = get_region_defaults(region)
    return {
        "region": region,
        "ip": anonymized_ip,
        "defaults": {
            "essential": rules["essential"],
            "functional": rules["functional"],
            "analytics": rules["analytics"],
            "marketing": rules["marketing"],
        },
        "require_explicit_opt_in": rules["require_explicit_opt_in"],
        "support_opt_out": rules["support_opt_out"],
    }


@router.get("/preferences", response_model=ConsentPreferencesResponse | None)
async def get_preferences(
    request: Request = None,
    anonymous_id: str | None = None,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Retrieve saved consent preferences for the logged-in user or anonymous identifier."""
    if current_user:
        stmt = select(ConsentPreference).where(ConsentPreference.user_id == current_user.id)
        result = await db.execute(stmt)
        pref = result.scalar_one_or_none()
        if pref:
            return pref

        # If logged in but no user_id record, check if we can merge an anonymous record
        if anonymous_id:
            stmt = select(ConsentPreference).where(
                ConsentPreference.anonymous_id == anonymous_id, ConsentPreference.user_id.is_(None)
            )
            result = await db.execute(stmt)
            anon_pref = result.scalar_one_or_none()
            if anon_pref:
                anon_pref.user_id = current_user.id
                anon_pref.updated_at = datetime.now(UTC).replace(tzinfo=None)

                # Write an audit log for the merge if request info is available
                ip = _get_client_ip(request) if request else "127.0.0.1"
                ip_hash = _hash_ip(ip)
                audit_log = ConsentAuditLog(
                    user_id=current_user.id,
                    anonymous_id=anonymous_id,
                    action="merge_anonymous_to_user",
                    old_value=None,
                    new_value={
                        "functional": anon_pref.functional,
                        "analytics": anon_pref.analytics,
                        "marketing": anon_pref.marketing,
                        "region": anon_pref.region,
                        "consent_version": anon_pref.consent_version,
                    },
                    ip_hash=ip_hash,
                    timestamp=anon_pref.updated_at,
                    consent_version=anon_pref.consent_version,
                )
                db.add(audit_log)
                await db.commit()
                return anon_pref

    if anonymous_id:
        stmt = select(ConsentPreference).where(
            ConsentPreference.anonymous_id == anonymous_id, ConsentPreference.user_id.is_(None)
        )
        result = await db.execute(stmt)
        return result.scalar_one_or_none()

    return None


@router.post("/preferences", response_model=ConsentPreferencesResponse)
async def save_preferences(
    body: ConsentPreferencesSaveRequest,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Save or update consent preferences. Merges anonymous preferences if logging in."""
    ip = _get_client_ip(request)
    ip_hash = _hash_ip(ip)
    now = datetime.now(UTC).replace(tzinfo=None)

    existing_pref = None
    old_value = None

    # 1. Search for existing preferences
    if current_user:
        # Check by user_id
        stmt = select(ConsentPreference).where(ConsentPreference.user_id == current_user.id)
        result = await db.execute(stmt)
        existing_pref = result.scalar_one_or_none()

        # If not found by user_id, check if there's an anonymous preference we need to merge
        if not existing_pref:
            stmt = select(ConsentPreference).where(
                ConsentPreference.anonymous_id == body.anonymous_id,
                ConsentPreference.user_id.is_(None),
            )
            result = await db.execute(stmt)
            existing_pref = result.scalar_one_or_none()
            if existing_pref:
                # Merge anonymous to user account
                existing_pref.user_id = current_user.id
    else:
        # Anonymous visitor
        stmt = select(ConsentPreference).where(
            ConsentPreference.anonymous_id == body.anonymous_id, ConsentPreference.user_id.is_(None)
        )
        result = await db.execute(stmt)
        existing_pref = result.scalar_one_or_none()

    # 2. Record old preferences for audit log
    if existing_pref:
        old_value = {
            "functional": existing_pref.functional,
            "analytics": existing_pref.analytics,
            "marketing": existing_pref.marketing,
            "region": existing_pref.region,
            "consent_version": existing_pref.consent_version,
        }
        # Update preference values
        existing_pref.functional = body.functional
        existing_pref.analytics = body.analytics
        existing_pref.marketing = body.marketing
        existing_pref.region = body.region
        existing_pref.consent_version = body.consent_version
        existing_pref.updated_at = now
    else:
        # Create new preference
        existing_pref = ConsentPreference(
            user_id=current_user.id if current_user else None,
            anonymous_id=body.anonymous_id,
            essential=True,
            functional=body.functional,
            analytics=body.analytics,
            marketing=body.marketing,
            region=body.region,
            consent_version=body.consent_version,
            accepted_at=now,
            updated_at=now,
        )
        db.add(existing_pref)

    await db.flush()

    # 3. Determine action type for GDPR audit compliance
    all_enabled = body.functional and body.analytics and body.marketing
    all_disabled = not body.functional and not body.analytics and not body.marketing

    if all_enabled:
        action = "accept_all"
    elif all_disabled:
        action = "reject_all"
    else:
        action = "update_settings"

    new_value = {
        "functional": body.functional,
        "analytics": body.analytics,
        "marketing": body.marketing,
        "region": body.region,
        "consent_version": body.consent_version,
    }

    # 4. Write ConsentAuditLog entry
    audit_log = ConsentAuditLog(
        user_id=current_user.id if current_user else None,
        anonymous_id=body.anonymous_id,
        action=action,
        old_value=old_value,
        new_value=new_value,
        ip_hash=ip_hash,
        timestamp=now,
        consent_version=body.consent_version,
    )
    db.add(audit_log)
    await db.commit()

    return existing_pref


@router.post("/withdraw", response_model=ConsentPreferencesResponse)
async def withdraw_consent(
    anonymous_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    current_user: User | None = Depends(get_current_user),
):
    """Withdraw all non-essential consents immediately (set to false)."""
    ip = _get_client_ip(request)
    ip_hash = _hash_ip(ip)
    now = datetime.now(UTC).replace(tzinfo=None)

    existing_pref = None
    old_value = None

    if current_user:
        stmt = select(ConsentPreference).where(ConsentPreference.user_id == current_user.id)
        result = await db.execute(stmt)
        existing_pref = result.scalar_one_or_none()
    else:
        stmt = select(ConsentPreference).where(
            ConsentPreference.anonymous_id == anonymous_id, ConsentPreference.user_id.is_(None)
        )
        result = await db.execute(stmt)
        existing_pref = result.scalar_one_or_none()

    if existing_pref:
        old_value = {
            "functional": existing_pref.functional,
            "analytics": existing_pref.analytics,
            "marketing": existing_pref.marketing,
            "region": existing_pref.region,
            "consent_version": existing_pref.consent_version,
        }
        existing_pref.functional = False
        existing_pref.analytics = False
        existing_pref.marketing = False
        existing_pref.updated_at = now
        consent_version = existing_pref.consent_version
    else:
        # Create standard empty preference
        consent_version = "default-withdrawn"
        existing_pref = ConsentPreference(
            user_id=current_user.id if current_user else None,
            anonymous_id=anonymous_id,
            essential=True,
            functional=False,
            analytics=False,
            marketing=False,
            region="ROW",
            consent_version=consent_version,
            accepted_at=now,
            updated_at=now,
        )
        db.add(existing_pref)

    await db.flush()

    new_value = {
        "functional": False,
        "analytics": False,
        "marketing": False,
        "region": existing_pref.region,
        "consent_version": consent_version,
    }

    audit_log = ConsentAuditLog(
        user_id=current_user.id if current_user else None,
        anonymous_id=anonymous_id,
        action="withdraw_consent",
        old_value=old_value,
        new_value=new_value,
        ip_hash=ip_hash,
        timestamp=now,
        consent_version=consent_version,
    )
    db.add(audit_log)
    await db.commit()

    return existing_pref


@router.get("/logs", response_model=list[ConsentAuditLogResponse])
async def get_consent_logs(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(require_user),
):
    """Retrieve all historical consent audit logs for the authenticated user (GDPR audit proof)."""
    stmt = (
        select(ConsentAuditLog)
        .where(ConsentAuditLog.user_id == current_user.id)
        .order_by(ConsentAuditLog.timestamp.desc())
    )
    result = await db.execute(stmt)
    return result.scalars().all()

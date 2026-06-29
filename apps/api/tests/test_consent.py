"""Unit tests for Consent Management Platform (CMP) endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.api.v1.consent import (
    detect_client_region,
    get_preferences,
    get_region_defaults,
    save_preferences,
    withdraw_consent,
)
from app.models.consent import ConsentAuditLog, ConsentPreference
from app.models.models import User
from app.schemas.consent import ConsentPreferencesSaveRequest


def test_detect_client_region():
    """Test regional detection and headers override heuristics."""
    # Test query param override
    req_override_query = MagicMock()
    req_override_query.headers = {}
    req_override_query.query_params = {"region": "eu"}
    assert detect_client_region(req_override_query) == "EU"

    # Test header override
    req_override_header = MagicMock()
    req_override_header.headers = {"x-consent-region-override": "uk"}
    req_override_header.query_params = {}
    assert detect_client_region(req_override_header) == "UK"

    # Test Cloudflare headers
    req_cf = MagicMock()
    req_cf.headers = {"cf-ipcountry": "fr"}
    req_cf.query_params = {}
    assert detect_client_region(req_cf) == "EU"

    # Test GB mapping to UK
    req_gb = MagicMock()
    req_gb.headers = {"cf-ipcountry": "gb"}
    req_gb.query_params = {}
    assert detect_client_region(req_gb) == "UK"

    # Test India mapping
    req_in = MagicMock()
    req_in.headers = {"x-vercel-ip-country": "in"}
    req_in.query_params = {}
    assert detect_client_region(req_in) == "IN"

    # Test California state detection
    req_ca = MagicMock()
    req_ca.headers = {"x-vercel-ip-country": "us", "x-vercel-ip-country-region": "ca"}
    req_ca.query_params = {}
    assert detect_client_region(req_ca) == "CA"

    # Test default fallback
    req_fallback = MagicMock()
    req_fallback.headers = {}
    req_fallback.query_params = {}
    assert detect_client_region(req_fallback) == "ROW"


def test_get_region_defaults():
    """Test defaults mappings per region."""
    eu_rules = get_region_defaults("EU")
    assert eu_rules["require_explicit_opt_in"] is True
    assert eu_rules["functional"] is False
    assert eu_rules["analytics"] is False

    ca_rules = get_region_defaults("CA")
    assert ca_rules["require_explicit_opt_in"] is False
    assert ca_rules["support_opt_out"] is True
    assert ca_rules["functional"] is True
    assert ca_rules["analytics"] is True
    assert ca_rules["marketing"] is True

    row_rules = get_region_defaults("ROW")
    assert row_rules["require_explicit_opt_in"] is False
    assert row_rules["support_opt_out"] is False
    assert row_rules["analytics"] is True
    assert row_rules["marketing"] is False


@pytest.mark.asyncio
async def test_get_preferences_authenticated(mock_db_session):
    """Test retrieving consent preferences for an authenticated user."""
    user = User(id=uuid.uuid4())
    pref = ConsentPreference(
        id=uuid.uuid4(),
        user_id=user.id,
        anonymous_id="anon-123",
        functional=True,
        analytics=False,
        marketing=False,
        region="EU",
        consent_version="2026-06-v1",
        accepted_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = pref
    mock_db_session.execute.return_value = mock_result

    response = await get_preferences(anonymous_id="anon-123", db=mock_db_session, current_user=user)
    assert response is not None
    assert response.user_id == user.id
    assert response.functional is True
    assert response.analytics is False


@pytest.mark.asyncio
async def test_get_preferences_anonymous(mock_db_session):
    """Test retrieving consent preferences for an anonymous visitor."""
    pref = ConsentPreference(
        id=uuid.uuid4(),
        user_id=None,
        anonymous_id="anon-123",
        functional=False,
        analytics=True,
        marketing=False,
        region="ROW",
        consent_version="2026-06-v1",
        accepted_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = pref
    mock_db_session.execute.return_value = mock_result

    response = await get_preferences(anonymous_id="anon-123", db=mock_db_session, current_user=None)
    assert response is not None
    assert response.user_id is None
    assert response.anonymous_id == "anon-123"
    assert response.analytics is True


@pytest.mark.asyncio
async def test_get_preferences_merges_anonymous_if_logged_in(mock_db_session):
    """Test that retrieving preferences for a logged-in user with no user pref but an active anonymous pref merges it."""
    user = User(id=uuid.uuid4())
    pref = ConsentPreference(
        id=uuid.uuid4(),
        user_id=None,
        anonymous_id="anon-123",
        functional=True,
        analytics=False,
        marketing=False,
        region="EU",
        consent_version="2026-06-v1",
        accepted_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    # First execute call (finding user pref) returns None
    # Second execute call (finding anonymous pref) returns pref
    mock_result_user = MagicMock()
    mock_result_user.scalar_one_or_none.return_value = None

    mock_result_anon = MagicMock()
    mock_result_anon.scalar_one_or_none.return_value = pref

    # Setup database execute mock to return user result first, then anonymous result
    mock_db_session.execute.side_effect = [mock_result_user, mock_result_anon]

    response = await get_preferences(
        request=None, anonymous_id="anon-123", db=mock_db_session, current_user=user
    )

    assert response is not None
    assert response.user_id == user.id
    assert response.anonymous_id == "anon-123"
    assert response.functional is True

    # Check that audit log was inserted
    assert mock_db_session.add.call_count == 1
    # Verify call arguments
    args, _ = mock_db_session.add.call_args_list[0]
    audit_log = args[0]
    assert isinstance(audit_log, ConsentAuditLog)
    assert audit_log.user_id == user.id
    assert audit_log.action == "merge_anonymous_to_user"


@pytest.mark.asyncio
async def test_save_preferences(mock_db_session):
    """Test saving consent preferences and producing an audit log."""
    user = User(id=uuid.uuid4())
    body = ConsentPreferencesSaveRequest(
        anonymous_id="anon-123",
        functional=True,
        analytics=True,
        marketing=False,
        region="EU",
        consent_version="2026-06-v1",
    )

    # Mock no existing pref
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_result

    # Mock request IP details
    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.client.host = "192.168.1.1"

    response = await save_preferences(
        body=body, request=mock_request, db=mock_db_session, current_user=user
    )

    assert response is not None
    assert response.user_id == user.id
    assert response.functional is True
    assert response.analytics is True
    assert response.marketing is False
    assert response.region == "EU"
    assert response.consent_version == "2026-06-v1"

    # Verify db.add is called for preference and audit log
    assert mock_db_session.add.call_count == 2


@pytest.mark.asyncio
async def test_withdraw_consent(mock_db_session):
    """Test withdrawing consent turns off non-essential categories."""
    user = User(id=uuid.uuid4())
    existing_pref = ConsentPreference(
        id=uuid.uuid4(),
        user_id=user.id,
        anonymous_id="anon-123",
        functional=True,
        analytics=True,
        marketing=True,
        region="CA",
        consent_version="2026-06-v1",
        accepted_at=datetime.now(UTC).replace(tzinfo=None),
        updated_at=datetime.now(UTC).replace(tzinfo=None),
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_pref
    mock_db_session.execute.return_value = mock_result

    mock_request = MagicMock()
    mock_request.headers = {}
    mock_request.client.host = "192.168.1.1"

    response = await withdraw_consent(
        anonymous_id="anon-123", request=mock_request, db=mock_db_session, current_user=user
    )

    assert response is not None
    assert response.functional is False
    assert response.analytics is False
    assert response.marketing is False
    assert response.region == "CA"

    # Verify db.add is called for audit log
    mock_db_session.add.assert_called_once()


@pytest.mark.asyncio
async def test_get_consent_logs(mock_db_session):
    """Test retrieving consent audit logs for an authenticated user."""
    user = User(id=uuid.uuid4())
    log = ConsentAuditLog(
        id=uuid.uuid4(),
        user_id=user.id,
        anonymous_id="anon-123",
        action="accept_all",
        new_value={"functional": True, "analytics": True, "marketing": True},
        ip_hash="hashed_ip",
        timestamp=datetime.now(UTC).replace(tzinfo=None),
        consent_version="2026-06-v1",
    )

    mock_scalars = MagicMock()
    mock_scalars.all.return_value = [log]
    mock_result = MagicMock()
    mock_result.scalars.return_value = mock_scalars
    mock_db_session.execute.return_value = mock_result

    from app.api.v1.consent import get_consent_logs

    response = await get_consent_logs(db=mock_db_session, current_user=user)
    assert len(response) == 1
    assert response[0].action == "accept_all"
    assert response[0].anonymous_id == "anon-123"

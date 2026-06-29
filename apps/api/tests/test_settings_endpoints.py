"""Unit tests for the settings page API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from app.api.v1.auth import change_password
from app.api.v1.users import (
    cancel_subscription,
    clear_all_history,
    clear_personalisation_data,
    delete_history_item,
    export_user_data,
    get_reading_history,
    mark_all_notifications_read,
    update_preferences,
    update_profile,
    upgrade_subscription,
)
from app.models.models import Category, Story, User, UserEvent, UserPreference
from app.schemas.user import ChangePasswordRequest, ProfileUpdateRequest, UserPreferencesUpdate


@pytest.mark.asyncio
async def test_update_preferences_with_ui_settings(mock_db_session):
    """Verify that update_preferences updates ui_settings correctly."""
    user = User(id=uuid.uuid4())
    prefs = UserPreference(id=uuid.uuid4(), user_id=user.id, ui_settings={"theme": "dark"})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = prefs
    mock_db_session.execute.return_value = mock_result

    body = UserPreferencesUpdate(ui_settings={"fontSize": "large"})
    response = await update_preferences(body=body, user=user, db=mock_db_session)

    assert response.message == "Preferences updated."
    assert prefs.ui_settings == {"theme": "dark", "fontSize": "large"}


@pytest.mark.asyncio
async def test_mark_all_notifications_read(mock_db_session):
    """Verify that mark_all_notifications_read marks notifications as read."""
    user = User(id=uuid.uuid4())
    response = await mark_all_notifications_read(user=user, db=mock_db_session)
    assert response.message == "All notifications marked as read."
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_get_reading_history(mock_db_session):
    """Verify reading history retrieves and maps event items correctly."""
    user = User(id=uuid.uuid4())
    story_id = uuid.uuid4()

    event = UserEvent(
        id=uuid.uuid4(),
        user_id=user.id,
        story_id=story_id,
        event_type="view_story",
        created_at=datetime.now(UTC),
    )

    story = Story(
        id=story_id,
        headline="Tech News Today",
        category=Category(slug="technology", name="Technology"),
        articles=[],
        created_at=datetime.now(UTC),
    )

    # Mock fetching user events
    mock_events_result = MagicMock()
    mock_events_result.scalars.return_value.all.return_value = [event]

    # Mock fetching story details
    mock_story_result = MagicMock()
    mock_story_result.scalar_one_or_none.return_value = story

    # Setup mock_db_session execute chain
    mock_db_session.execute.side_effect = [mock_events_result, mock_story_result]

    response = await get_reading_history(user=user, db=mock_db_session)
    assert len(response) == 1
    assert response[0]["title"] == "Tech News Today"
    assert response[0]["category"] == "Technology"
    assert response[0]["catClass"] == "bt"
    assert response[0]["isToday"] is True


@pytest.mark.asyncio
async def test_delete_history_item(mock_db_session):
    """Verify individual history items can be deleted."""
    user = User(id=uuid.uuid4())
    event_id = uuid.uuid4()
    event = UserEvent(id=event_id, user_id=user.id)

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = event
    mock_db_session.execute.return_value = mock_result

    response = await delete_history_item(event_id=event_id, user=user, db=mock_db_session)
    assert response.message == "History item removed."
    mock_db_session.delete.assert_called_once_with(event)


@pytest.mark.asyncio
async def test_clear_all_history(mock_db_session):
    """Verify reading history can be cleared."""
    user = User(id=uuid.uuid4())
    response = await clear_all_history(user=user, db=mock_db_session)
    assert response.message == "Reading history cleared."
    mock_db_session.execute.assert_called_once()


@pytest.mark.asyncio
async def test_upgrade_subscription(mock_db_session):
    """Verify user plan is upgraded to pro."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role="user",
        subscription_plan="free",
        status="active",
        email_verified=True,
    )
    response = await upgrade_subscription(user=user, db=mock_db_session)
    assert response.subscription_plan == "pro"


@pytest.mark.asyncio
async def test_cancel_subscription(mock_db_session):
    """Verify user plan is downgraded to free."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role="user",
        subscription_plan="pro",
        status="active",
        email_verified=True,
    )
    response = await cancel_subscription(user=user, db=mock_db_session)
    assert response.subscription_plan == "free"


@pytest.mark.asyncio
async def test_export_user_data(mock_db_session):
    """Verify user data export returns a valid response."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role="user",
        subscription_plan="free",
        status="active",
        email_verified=True,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_result.scalar_one_or_none.return_value = None
    mock_db_session.execute.return_value = mock_result

    response = await export_user_data(user=user, db=mock_db_session)
    assert response.status_code == 200
    assert "newsiq_data_export_" in response.headers["Content-Disposition"]


@pytest.mark.asyncio
async def test_clear_personalisation_data(mock_db_session):
    """Verify personalisation data can be cleared."""
    user = User(id=uuid.uuid4())
    prefs = UserPreference(id=uuid.uuid4(), user_id=user.id, ui_settings={"trackClick": False})

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = prefs
    mock_db_session.execute.side_effect = [None, None, mock_result]

    response = await clear_personalisation_data(user=user, db=mock_db_session)
    assert response.message == "Personalisation data successfully cleared."
    assert prefs.ui_settings["trackClick"] is True


@pytest.mark.asyncio
@patch("app.core.security.verify_password")
@patch("app.core.security.hash_password")
@patch("app.api.v1.auth.AuthService.logout_all")
async def test_change_password(mock_logout_all, mock_hash_password, mock_verify_password, mock_db_session):
    """Verify that password can be changed successfully."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        role="user",
        password_hash="old_hash",
        status="active",
        email_verified=True,
    )
    mock_verify_password.return_value = True
    mock_hash_password.return_value = "new_hash"
    mock_logout_all.return_value = AsyncMock()

    body = ChangePasswordRequest(current_password="old_password", new_password="NewSecurePassword123!")
    response = await change_password(body=body, user=user, db=mock_db_session)

    assert response.message == "Password changed successfully."
    assert user.password_hash == "new_hash"
    mock_logout_all.assert_called_once_with(user.id)


@pytest.mark.asyncio
async def test_update_profile(mock_db_session):
    """Verify that update_profile updates user name and image correctly and sets a naive updated_at timestamp."""
    user = User(
        id=uuid.uuid4(),
        email="test@example.com",
        name="Old Name",
        image_url="old_url",
        role="user",
        subscription_plan="free",
        status="active",
        email_verified=True,
    )
    body = ProfileUpdateRequest(name="New Name", image_url="new_url")
    response = await update_profile(body=body, user=user, db=mock_db_session)

    assert response.name == "New Name"
    assert response.image_url == "new_url"
    assert user.updated_at is not None
    assert user.updated_at.tzinfo is None  # Check that it is naive

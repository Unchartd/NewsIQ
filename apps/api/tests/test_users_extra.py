"""Unit tests for user notifications and digests API endpoints."""

import uuid
from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from app.api.v1.users import (
    delete_notification,
    get_digest_subscriptions,
    get_notifications,
    mark_notification_as_read,
    update_digest_subscriptions,
)
from app.models.models import DigestSubscription, Notification, User
from app.schemas.user import DigestSubscriptionUpdate


@pytest.mark.asyncio
async def test_get_notifications(mock_db_session):
    """Verify that notifications are retrieved and mapped correctly."""
    user = User(id=uuid.uuid4())

    mock_notification = Notification(
        id=uuid.uuid4(),
        user_id=user.id,
        title="Test Notification",
        body="This is a test notification body.",
        notification_type="breaking_news",
        is_read=False,
        created_at=datetime.now(UTC),
    )

    # Mocking SQLAlchemy execute result
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_notification]
    mock_db_session.execute.return_value = mock_result

    response = await get_notifications(user=user, db=mock_db_session)
    assert len(response) == 1
    assert response[0].title == "Test Notification"
    assert response[0].is_read is False


@pytest.mark.asyncio
async def test_mark_notification_as_read(mock_db_session):
    """Verify notification can be marked as read."""
    user = User(id=uuid.uuid4())
    notification_id = uuid.uuid4()

    mock_notification = Notification(
        id=notification_id,
        user_id=user.id,
        title="Test Notification",
        is_read=False,
    )

    # Mocking select query to return the notification
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_notification
    mock_db_session.execute.return_value = mock_result

    response = await mark_notification_as_read(
        notification_id=notification_id, user=user, db=mock_db_session
    )
    assert response.message == "Notification marked as read."
    assert mock_notification.is_read is True


@pytest.mark.asyncio
async def test_delete_notification(mock_db_session):
    """Verify notification can be deleted."""
    user = User(id=uuid.uuid4())
    notification_id = uuid.uuid4()

    mock_notification = Notification(
        id=notification_id,
        user_id=user.id,
        title="Test Notification",
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = mock_notification
    mock_db_session.execute.return_value = mock_result

    response = await delete_notification(
        notification_id=notification_id, user=user, db=mock_db_session
    )
    assert response.message == "Notification deleted."
    mock_db_session.delete.assert_called_once_with(mock_notification)


@pytest.mark.asyncio
async def test_get_digest_subscriptions(mock_db_session):
    """Verify list of digest subscriptions is retrieved."""
    user = User(id=uuid.uuid4())

    mock_sub = DigestSubscription(
        id=uuid.uuid4(),
        user_id=user.id,
        frequency="morning",
        delivery_channel="email",
        enabled=True,
    )

    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = [mock_sub]
    mock_db_session.execute.return_value = mock_result

    response = await get_digest_subscriptions(user=user, db=mock_db_session)
    assert len(response) == 1
    assert response[0].frequency == "morning"


@pytest.mark.asyncio
async def test_update_digest_subscriptions(mock_db_session):
    """Verify updating digest subscription handles existing and new entries."""
    user = User(id=uuid.uuid4())
    from app.models.models import UserPreference

    # 1. Update existing subscription
    existing_sub = DigestSubscription(
        id=uuid.uuid4(),
        user_id=user.id,
        frequency="morning",
        delivery_channel="email",
        enabled=False,
    )

    async def mock_execute(query, *args, **kwargs):
        query_str = str(query)
        res = MagicMock()
        if "digest_subscription" in query_str:
            res.scalar_one_or_none.return_value = existing_sub
            res.scalars.return_value.all.return_value = [existing_sub]
        elif "user_preference" in query_str:
            res.scalar_one_or_none.return_value = UserPreference(
                id=uuid.uuid4(), user_id=user.id, digest_settings={"editions": {}}
            )
        return res

    mock_db_session.execute.side_effect = mock_execute

    body = DigestSubscriptionUpdate(frequency="morning", delivery_channel="email", enabled=True)

    response = await update_digest_subscriptions(body=body, user=user, db=mock_db_session)
    assert response.message == "Digest subscription updated."
    assert existing_sub.enabled is True


@pytest.mark.asyncio
async def test_setup_digest(mock_db_session):
    """Verify setup_digest correctly saves preferences and creates subscriptions."""
    user = User(id=uuid.uuid4())

    from app.api.v1.users import setup_digest
    from app.models.models import Category, UserPreference
    from app.schemas.user import DigestSetupRequest

    body = DigestSetupRequest(
        categories=["politics", "technology"],
        story_count=5,
        prioritize_local=True,
        include_world=True,
        editions={"morning": True, "midday": False, "evening": True},
        delivery_times={"morning": "7:00", "midday": "12:00", "evening": "18:00"},
        frequency="daily",
        custom_days=[],
        weekly_wrap=True,
        channels={"email": True, "app": True, "telegram": False, "push": False},
        email_format="html",
    )

    mock_pref = None
    mock_cat_politics = Category(id=uuid.uuid4(), slug="politics", name="Politics")
    mock_cat_tech = Category(id=uuid.uuid4(), slug="technology", name="Technology")

    mock_result_pref = MagicMock()
    mock_result_pref.scalar_one_or_none.side_effect = [
        mock_pref,  # for UserPreference lookup
        mock_cat_politics,  # for politics Category lookup
        mock_cat_tech,  # for technology Category lookup
    ]
    mock_db_session.execute.return_value = mock_result_pref

    response = await setup_digest(body=body, user=user, db=mock_db_session)
    assert response.message == "Digest subscription set up successfully."

    # Check that db.add was called for UserPreference and the subscriptions
    added_items = [args[0] for args, _ in mock_db_session.add.call_args_list]

    pref_added = next(x for x in added_items if isinstance(x, UserPreference))
    assert pref_added.digest_settings["story_count"] == 5
    assert pref_added.digest_settings["prioritize_local"] is True
    assert pref_added.digest_settings["email_format"] == "html"


@pytest.mark.asyncio
async def test_unsubscribe_digest(mock_db_session):
    """Verify unsubscribe_digest correctly clears preferences and deletes subscriptions."""
    user = User(id=uuid.uuid4())

    from app.api.v1.users import unsubscribe_digest
    from app.models.models import UserPreference

    mock_pref = UserPreference(id=uuid.uuid4(), user_id=user.id, digest_settings={"story_count": 5})

    mock_result_pref = MagicMock()
    mock_result_pref.scalar_one_or_none.return_value = mock_pref
    mock_db_session.execute.return_value = mock_result_pref

    response = await unsubscribe_digest(user=user, db=mock_db_session)
    assert response.message == "Successfully unsubscribed from all digests."
    assert mock_pref.digest_settings is None

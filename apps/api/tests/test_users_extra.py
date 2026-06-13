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

    # 1. Update existing subscription
    existing_sub = DigestSubscription(
        id=uuid.uuid4(),
        user_id=user.id,
        frequency="morning",
        delivery_channel="email",
        enabled=False,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = existing_sub
    mock_db_session.execute.return_value = mock_result

    body = DigestSubscriptionUpdate(frequency="morning", delivery_channel="email", enabled=True)

    response = await update_digest_subscriptions(body=body, user=user, db=mock_db_session)
    assert response.message == "Digest subscription updated."
    assert existing_sub.enabled is True

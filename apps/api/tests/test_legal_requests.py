"""Legal, privacy, copyright, abuse and contact requests must actually arrive.

The website's forms used to show "Request submitted successfully. Our legal
department will review within 72 hours" and send nothing — privacy requests
and copyright notices were discarded in the browser.
"""

from unittest.mock import AsyncMock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from app.core.config import settings
from app.main import app
from app.services.email_service import EmailService

VALID = {
    "kind": "copyright",
    "email": "rights@publisher.example",
    "name": "Rights Desk",
    "subject": "Takedown request",
    "request_type": "takedown",
    "reference_url": "https://newsiq.online/story/example",
    "details": "Our article was reproduced beyond a summary; please remove it.",
}


@pytest.fixture
async def client():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


async def test_a_request_is_delivered_to_the_monitored_inbox(client):
    with patch.object(EmailService, "_send", AsyncMock()) as send:
        r = await client.post(f"{settings.API_V1_PREFIX}/legal/requests", json=VALID)

    assert r.status_code == 202
    reference = r.json()["reference"]
    assert reference.startswith("NIQ-")

    args, kwargs = send.await_args
    recipient, subject, _html, text = args[:4]
    assert recipient == settings.LEGAL_CONTACT_EMAIL
    assert reference in subject and "copyright" in subject
    assert "rights@publisher.example" in text and VALID["details"] in text
    assert kwargs["reply_to"] == "rights@publisher.example", "replies must reach the requester"
    assert kwargs["raise_errors"] is True


async def test_a_delivery_failure_is_reported_not_hidden(client):
    with patch.object(EmailService, "_send", AsyncMock(side_effect=OSError("smtp down"))):
        r = await client.post(f"{settings.API_V1_PREFIX}/legal/requests", json=VALID)

    assert r.status_code == 503
    assert settings.LEGAL_CONTACT_EMAIL in r.json()["detail"], "the user needs a way through"


async def test_the_honeypot_drops_bots_without_telling_them(client):
    with patch.object(EmailService, "_send", AsyncMock()) as send:
        r = await client.post(
            f"{settings.API_V1_PREFIX}/legal/requests", json=VALID | {"website": "spam.example"}
        )
    assert r.status_code == 202
    send.assert_not_awaited()


@pytest.mark.parametrize(
    "bad",
    [
        {"kind": "marketing"},
        {"email": "not-an-email"},
        {"details": "short"},
        {"details": "x" * 5001},
    ],
)
async def test_invalid_requests_are_rejected(client, bad):
    with patch.object(EmailService, "_send", AsyncMock()) as send:
        r = await client.post(f"{settings.API_V1_PREFIX}/legal/requests", json=VALID | bad)
    assert r.status_code == 422
    send.assert_not_awaited()


async def test_user_supplied_text_cannot_inject_html_into_the_email():
    with patch.object(EmailService, "_send", AsyncMock()) as send:
        await EmailService().send_legal_request(
            reference="NIQ-TEST",
            kind="contact",
            request_type=None,
            requester_email="a@b.example",
            name="<img src=x onerror=alert(1)>",
            subject=None,
            details="<script>alert(1)</script> hello there",
            reference_url=None,
        )
    html = send.await_args.args[2]
    assert "<script>" not in html and "&lt;script&gt;" in html

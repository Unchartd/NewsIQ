"""SSE observability endpoints must require an admin.

Both streaming endpoints declared no auth dependency, while the admin UI
appended the access token to the URL (`?token=...`, pipeline/page.tsx:144). The
backend never read it, so the credential was written into access logs and
provided no protection: live pipeline logs and status transitions — article
URLs, story ids, stage errors and tracebacks — were readable by anyone able to
reach the API. The sibling non-streaming logs endpoint has always required an
admin, so this was an oversight rather than a deliberate policy.
"""

import inspect
import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import HTTPException

from app.api.v1 import admin
from app.core.deps import require_admin_sse


def _request(cookies=None):
    req = MagicMock()
    req.cookies = cookies or {}
    return req


def _db_returning(user):
    db = AsyncMock()
    result = MagicMock()
    result.scalar_one_or_none.return_value = user
    db.execute.return_value = result
    return db


def _admin_user():
    u = MagicMock()
    u.id = uuid.uuid4()
    u.role = "admin"
    u.status = "active"
    return u


@pytest.mark.parametrize("endpoint", ["stream_stage_run_logs", "stream_pipeline_status"])
def test_both_streaming_endpoints_declare_admin_auth(endpoint):
    """Regression guard: neither may go back to having no dependency."""
    sig = inspect.signature(getattr(admin, endpoint))
    defaults = [p.default for p in sig.parameters.values()]
    assert any(getattr(d, "dependency", None) is require_admin_sse for d in defaults), (
        f"{endpoint} does not require an admin — live telemetry would be public"
    )


@pytest.mark.asyncio
async def test_missing_token_is_rejected():
    with pytest.raises(HTTPException) as exc:
        await require_admin_sse(request=_request(), token=None, credentials=None, db=AsyncMock())
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_query_token_is_actually_validated(monkeypatch):
    """The token the UI sends must be decoded, not merely accepted."""
    monkeypatch.setattr("app.core.deps.decode_token", lambda t: None)

    with pytest.raises(HTTPException) as exc:
        await require_admin_sse(
            request=_request(), token="forged", credentials=None, db=AsyncMock()
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_non_admin_with_a_valid_token_is_forbidden(monkeypatch):
    monkeypatch.setattr(
        "app.core.deps.decode_token", lambda t: {"type": "access", "sub": str(uuid.uuid4())}
    )
    user = _admin_user()
    user.role = "user"

    with pytest.raises(HTTPException) as exc:
        await require_admin_sse(
            request=_request(), token="valid", credentials=None, db=_db_returning(user)
        )
    assert exc.value.status_code == 403


@pytest.mark.asyncio
async def test_refresh_token_cannot_be_used_to_stream(monkeypatch):
    monkeypatch.setattr(
        "app.core.deps.decode_token", lambda t: {"type": "refresh", "sub": str(uuid.uuid4())}
    )
    with pytest.raises(HTTPException) as exc:
        await require_admin_sse(
            request=_request(), token="refresh", credentials=None, db=AsyncMock()
        )
    assert exc.value.status_code == 401


@pytest.mark.asyncio
async def test_valid_admin_query_token_is_accepted(monkeypatch):
    """EventSource cannot set headers, so the query parameter must still work."""
    monkeypatch.setattr(
        "app.core.deps.decode_token", lambda t: {"type": "access", "sub": str(uuid.uuid4())}
    )
    user = _admin_user()
    got = await require_admin_sse(
        request=_request(), token="valid", credentials=None, db=_db_returning(user)
    )
    assert got is user

"""Service utility to record story cluster mutation events (Story Evolution)."""

import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.trace import run_id_ctx
from app.models.observability_models import StoryEvolutionModel


async def record_story_evolution(
    db: AsyncSession,
    story_id: uuid.UUID | None,
    event_type: str,
    article_id: uuid.UUID | None = None,
    parent_story_ids: list[str] | None = None,
    child_story_ids: list[str] | None = None,
    before_state: dict[str, Any] | None = None,
    after_state: dict[str, Any] | None = None,
    notes: str | None = None,
    run_id: uuid.UUID | None = None,
) -> None:
    """Record a story cluster mutation event (Story Evolution) in Postgres.

    Uses trace run context if run_id is not explicitly passed.
    """
    resolved_run_id = run_id
    if not resolved_run_id:
        ctx_id = run_id_ctx.get(None)
        if ctx_id:
            try:
                resolved_run_id = uuid.UUID(ctx_id) if isinstance(ctx_id, str) else ctx_id
            except Exception:
                pass

    evo = StoryEvolutionModel(
        id=uuid.uuid4(),
        run_id=resolved_run_id,
        story_id=story_id,
        event_type=event_type,
        article_id=article_id,
        parent_story_ids=parent_story_ids,
        child_story_ids=child_story_ids,
        before_state=before_state,
        after_state=after_state,
        notes=notes,
        created_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(evo)
    await db.flush()

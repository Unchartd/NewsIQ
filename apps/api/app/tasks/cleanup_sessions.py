"""Background task for cleaning up expired sessions."""

import logging

from app.core.database import async_session_factory
from app.services.session_service import SessionService
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


async def cleanup_expired_sessions_task_impl() -> int:
    """Implement session cleanup asynchronously."""
    async with async_session_factory() as db:
        session_service = SessionService(db)
        count = await session_service.cleanup_expired_sessions()
        logger.info("Cleaned up %d expired sessions.", count)
        return count


@celery_app.task(name="app.tasks.cleanup_sessions.cleanup_expired_sessions_task")
def cleanup_expired_sessions_task() -> int:
    """Celery task wrapper for expired sessions cleanup."""
    from app.workers.tasks import run_async

    return run_async(cleanup_expired_sessions_task_impl())

import asyncio
import logging
from collections.abc import Coroutine
from datetime import datetime
from typing import Any

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.models import DigestSubscription, UserPreference
from app.services.digest_service import digest_delivery_service
from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro: Coroutine[Any, Any, Any]) -> Any:
    """Helper to run async coroutines in synchronous Celery tasks."""
    try:
        return asyncio.run(coro)
    except RuntimeError:
        # Event loop is already running in this thread
        loop = asyncio.get_event_loop()
        return loop.run_until_complete(coro)


@celery_app.task(name="app.workers.digest_tasks.process_hourly_digests_task")
def process_hourly_digests_task() -> int:
    """Hourly background task to check and deliver news digests according to user schedules."""
    logger.info("Celery task: Checking hourly digest delivery schedules.")

    async def _run():
        now = datetime.now()
        current_hour = now.hour
        current_weekday = now.weekday()  # 6 is Sunday

        # Gather active subscriptions to determine frequencies we need to process
        async with async_session_factory() as session:
            stmt = select(DigestSubscription).where(DigestSubscription.enabled)
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()

            if not subscriptions:
                logger.info("No active digest subscriptions found.")
                return 0

            # Map user preferences to determine if they need delivery now
            triggered_frequencies_by_user: dict[str, list[str]] = {}

            for sub in subscriptions:
                # Get the user's UserPreference
                pref_stmt = select(UserPreference).where(UserPreference.user_id == sub.user_id)
                pref_res = await session.execute(pref_stmt)
                prefs = pref_res.scalar_one_or_none()

                if not prefs or not prefs.digest_settings:
                    continue

                delivery_times = prefs.digest_settings.get("delivery_times", {})
                pref_time = delivery_times.get(sub.frequency, "07:00")

                try:
                    pref_hour = int(pref_time.split(":")[0])
                except Exception:
                    pref_hour = 7
                    if sub.frequency == "midday":
                        pref_hour = 13
                    elif sub.frequency == "evening":
                        pref_hour = 18
                    elif sub.frequency == "weekly":
                        pref_hour = 9

                if current_hour == pref_hour:
                    # For weekly wrap-up, also verify that today is Sunday (weekday 6)
                    if sub.frequency == "weekly" and current_weekday != 6:
                        continue

                    if sub.frequency not in triggered_frequencies_by_user:
                        triggered_frequencies_by_user[sub.frequency] = []
                    triggered_frequencies_by_user[sub.frequency].append(sub.user_id)

            total_delivered = 0
            # Process delivery for each matched frequency
            for freq, user_ids in triggered_frequencies_by_user.items():
                logger.info(
                    "Triggering digest compilation and delivery for frequency '%s' for %d users.",
                    freq,
                    len(user_ids),
                )
                delivered = await digest_delivery_service.compile_and_deliver_digests(session, freq)
                total_delivered += delivered

            return total_delivered

    return run_async(_run())


@celery_app.task(name="app.workers.digest_tasks.trigger_digest_delivery_now_task")
def trigger_digest_delivery_now_task(frequency: str) -> int:
    """Task to trigger delivery of digests for a given frequency/edition immediately."""
    logger.info("Celery task: Manually triggering digest delivery for frequency '%s'.", frequency)

    async def _run():
        async with async_session_factory() as session:
            delivered = await digest_delivery_service.compile_and_deliver_digests(
                session, frequency
            )
            return delivered

    return run_async(_run())

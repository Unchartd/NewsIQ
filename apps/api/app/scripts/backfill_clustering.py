"""One-off backfill: cluster articles that were processed before the age bound existed.

Context
-------
Batch clustering bounds eligibility at PIPELINE_MAX_ARTICLE_AGE_HOURS (72h by
default) so stale news cannot resurface as new stories. That bound was added
while the pipeline had been down for 9 days, which left ~4,151 articles that
are fully embedded and event-extracted, belong to no story, and are now too
old to ever be picked up — work already paid for that would otherwise be
discarded.

This script runs the normal clustering path against a widened window so that
backlog can form stories once. It is not scheduled and should not be: the age
bound is correct for steady-state operation.

Usage
-----
    python -m app.scripts.backfill_clustering --max-age-hours 720 --rounds 5
    python -m app.scripts.backfill_clustering --dry-run

Safety
------
* --dry-run reports what is eligible and exits without writing.
* Each round clusters at most _BATCH_LIMIT (200) articles, so progress is
  incremental and interruptible; re-running resumes where it left off because
  eligibility is defined by absence from story_articles.
* Synthesis runs per cluster and costs LLM spend. Start with --rounds 1 and
  check the result before widening.
"""

import argparse
import asyncio
import logging

from sqlalchemy import text

from app.core.database import async_session_factory
from app.services.clustering_service import clustering_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("backfill_clustering")

_ELIGIBLE_SQL = """
SELECT count(*) FROM articles a
WHERE a.embedding_status = 'completed'
  AND a.event_extraction_status = 'completed'
  AND a.created_at >= (now() AT TIME ZONE 'utc') - make_interval(hours => :hours)
  AND NOT EXISTS (SELECT 1 FROM story_articles sa WHERE sa.article_id = a.id)
"""


async def _eligible_count(hours: int) -> int:
    async with async_session_factory() as session:
        result = await session.execute(text(_ELIGIBLE_SQL), {"hours": hours})
        return int(result.scalar() or 0)


async def run(max_age_hours: int, rounds: int, dry_run: bool) -> int:
    eligible = await _eligible_count(max_age_hours)
    logger.info(
        "Eligible articles within a %dh window: %d (normal window would be far fewer)",
        max_age_hours,
        eligible,
    )

    if dry_run:
        logger.info("--dry-run: nothing written.")
        return 0

    if eligible == 0:
        logger.info("Nothing to backfill.")
        return 0

    total_stories = 0
    for round_num in range(1, rounds + 1):
        async with async_session_factory() as session:
            created = await clustering_service.run_batch_clustering(
                session, max_age_hours=max_age_hours
            )
        total_stories += created
        remaining = await _eligible_count(max_age_hours)
        logger.info(
            "Round %d/%d: created %d stories (%d articles still eligible)",
            round_num,
            rounds,
            created,
            remaining,
        )
        if created == 0 or remaining == 0:
            logger.info("Converged — stopping early.")
            break

    logger.info("Backfill complete: %d stories created.", total_stories)
    return total_stories


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--max-age-hours",
        type=int,
        default=720,
        help="Widened eligibility window for this run only (default: 720 = 30 days).",
    )
    parser.add_argument(
        "--rounds",
        type=int,
        default=1,
        help="Clustering passes to run; each handles up to 200 articles (default: 1).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Report eligible article count and exit without writing.",
    )
    args = parser.parse_args()

    asyncio.run(run(args.max_age_hours, args.rounds, args.dry_run))


if __name__ == "__main__":
    main()

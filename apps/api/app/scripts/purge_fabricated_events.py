"""One-off remediation for the fabricated-event incident.

Context
-------
Between 2026-07-15 and 2026-07-31 the mock LLM provider served event
extraction during quota exhaustion and 6,584 identical template events
('POLICY' / ['Officials'] / ['Public interest'] / 'United States' / no date)
were persisted as real — 86% of the primary-event table. On 2026-08-12 a
clustering backfill consumed that data and fused hundreds of unrelated
articles into giant stories (193 and 88 articles).

What this does (in one reviewed pass, dry-run by default)
---------------------------------------------------------
1. Deletes stories created by the poisoned backfill window (created_at >=
   --stories-since, batch-created) together with their child rows, returning
   their articles to the unclustered pool.
2. Deletes ALL article_events and article_entities for articles whose primary
   event carries the fabricated fingerprint — the same extraction call
   produced the events AND the entities, so both are fabricated.
3. Resets those articles' event_extraction_status to 'pending'. The pipeline's
   own age window then decides: recent articles are re-extracted with real
   providers; older ones are retired to 'skipped' by the hourly task. No
   unbounded LLM spend.

Pre-2026-08 stories are NOT touched: they embed fabricated data too, but they
are long-standing published content — removing them is a product decision.

Usage
-----
    python -m app.scripts.purge_fabricated_events                # dry run
    python -m app.scripts.purge_fabricated_events --execute
"""

import argparse
import asyncio
import logging
from datetime import datetime

from sqlalchemy import text

from app.core.database import async_session_factory

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("purge_fabricated_events")

FABRICATED_FP = "97f02dad9bf2bbda2a9677119afe8375"

_COUNTS = {
    "stories to delete": ("SELECT count(*) FROM stories WHERE created_at >= :since"),
    "story_articles to unlink": (
        "SELECT count(*) FROM story_articles sa JOIN stories s ON s.id = sa.story_id "
        "WHERE s.created_at >= :since"
    ),
    "articles with fabricated events": (
        "SELECT count(DISTINCT article_id) FROM article_events WHERE event_fingerprint = :fp"
    ),
    "fabricated event rows (all events of those articles)": (
        "SELECT count(*) FROM article_events WHERE article_id IN "
        "(SELECT article_id FROM article_events WHERE event_fingerprint = :fp)"
    ),
    "entity rows from the same extractions": (
        "SELECT count(*) FROM article_entities WHERE article_id IN "
        "(SELECT article_id FROM article_events WHERE event_fingerprint = :fp)"
    ),
}

# Every table with a ForeignKey to stories.id (verified against the models),
# cleaned before their parent stories. story_articles is in the list so the
# articles return to the unclustered pool. bookmarks/user_events/story_reviews
# are included for completeness — hours-old auto-created stories have none,
# but a stray row must not abort the transaction. story_candidates carries a
# nullable story_id and is detached, not deleted.
_STORY_CHILD_TABLES = [
    "story_timeline_events",
    "story_source_coverage",
    "story_differences",
    "story_entities",
    "story_tags",
    "story_contradictions",
    "story_metrics",
    "story_versions",
    "story_evolutions",
    "synthesis_artifacts",
    "story_reviews",
    "bookmarks",
    "user_events",
    "story_articles",
]


async def run(stories_since: datetime, execute: bool) -> None:
    params = {"since": stories_since, "fp": FABRICATED_FP}

    async with async_session_factory() as session:
        logger.info("--- scope (stories_since=%s) ---", stories_since)
        for name, sql in _COUNTS.items():
            n = (await session.execute(text(sql), params)).scalar()
            logger.info("%-52s %s", name, n)

        if not execute:
            logger.info("DRY RUN — nothing changed. Re-run with --execute to apply.")
            return

        # 1a. Break the circular FK first: stories.current_version_id references
        #     story_versions, which we are about to delete.
        await session.execute(
            text("UPDATE stories SET current_version_id = NULL WHERE created_at >= :since"),
            params,
        )
        # 1b. Detach nullable references that must survive the delete.
        await session.execute(
            text(
                "UPDATE story_candidates SET story_id = NULL WHERE story_id IN "
                "(SELECT id FROM stories WHERE created_at >= :since)"
            ),
            params,
        )

        # 1c. Poisoned-window stories and children
        for table in _STORY_CHILD_TABLES:
            res = await session.execute(
                text(
                    f"DELETE FROM {table} WHERE story_id IN "  # noqa: S608 — fixed identifier list
                    "(SELECT id FROM stories WHERE created_at >= :since)"
                ),
                params,
            )
            logger.info("deleted %-6s rows from %s", getattr(res, "rowcount", 0), table)
        res = await session.execute(text("DELETE FROM stories WHERE created_at >= :since"), params)
        logger.info("deleted %s stories", getattr(res, "rowcount", 0))

        # 2. Fabricated events + sibling entities, then reset extraction status
        res = await session.execute(
            text(
                "DELETE FROM article_entities WHERE article_id IN "
                "(SELECT article_id FROM article_events WHERE event_fingerprint = :fp)"
            ),
            params,
        )
        logger.info("deleted %s fabricated entity rows", getattr(res, "rowcount", 0))

        await session.execute(
            text(
                "CREATE TEMP TABLE _fab_articles AS "
                "SELECT DISTINCT article_id FROM article_events WHERE event_fingerprint = :fp"
            ),
            params,
        )
        res = await session.execute(
            text(
                "DELETE FROM article_events WHERE article_id IN "
                "(SELECT article_id FROM _fab_articles)"
            )
        )
        logger.info("deleted %s fabricated event rows", getattr(res, "rowcount", 0))

        res = await session.execute(
            text(
                "UPDATE articles SET event_extraction_status = 'pending' "
                "WHERE id IN (SELECT article_id FROM _fab_articles)"
            )
        )
        logger.info(
            "reset %s articles to event_extraction_status='pending'", getattr(res, "rowcount", 0)
        )

        await session.commit()
        logger.info("REMEDIATION COMMITTED.")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--stories-since",
        default="2026-08-11 22:50:00",
        help="UTC timestamp; stories created at/after this are deleted "
        "(default: start of the poisoned backfill window).",
    )
    parser.add_argument("--execute", action="store_true", help="Apply changes (default: dry run).")
    args = parser.parse_args()
    # asyncpg needs a real datetime, not a string
    since = datetime.fromisoformat(args.stories_since)
    asyncio.run(run(since, args.execute))


if __name__ == "__main__":
    main()

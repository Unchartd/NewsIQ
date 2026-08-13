"""Re-synthesise stories whose three summaries are byte-identical.

Why this is needed
------------------
When the model returned a single "summary" field instead of the three-tier
fields, the gateway's schema cleaner copied that one value into
one_line_summary, short_summary AND detailed_summary. Validation then passed,
so nothing retried: three summaries were stored where the model produced one,
and the tab labelled "1-line summary" rendered a full paragraph (up to 1439
characters in production).

The coercion and the prompt are fixed forward, but rows written before the fix
keep their duplicated text. Nothing in the pipeline re-summarises a story that
already has a summary, so they stay wrong until re-synthesised here.

Safety
------
* Dry run by default; --execute is required to write.
* Only touches stories where all three summaries are non-null AND identical —
  the exact signature of the bug. Correctly tiered stories are never rewritten.
* Uses the SAME orchestrator production uses, so the result is exactly what the
  live path would now produce. No bespoke summarisation.
* Re-reads each story afterwards and reports whether it is still duplicated,
  so a silent second failure cannot look like success.
* Costs LLM budget: one full synthesis per story, subject to the orchestrator's
  own daily budget gate.

Usage
-----
    python -m app.scripts.resynthesize_duplicate_summaries
    python -m app.scripts.resynthesize_duplicate_summaries --execute
    python -m app.scripts.resynthesize_duplicate_summaries --execute --limit 4
"""

import argparse
import asyncio
import logging
import uuid

from sqlalchemy import select

from app.core.database import async_session_factory
from app.models.models import Story

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
logger = logging.getLogger(__name__)


DUPLICATE_FILTER = (
    Story.one_line_summary.isnot(None)
    & (Story.one_line_summary == Story.short_summary)
    & (Story.short_summary == Story.detailed_summary)
)


async def find_duplicates(session, limit: int) -> list[Story]:
    """Stories carrying the bug signature: all three summaries identical."""
    stmt = select(Story).where(DUPLICATE_FILTER).order_by(Story.created_at.desc()).limit(limit)
    return list((await session.execute(stmt)).scalars().all())


async def verify(story_id: uuid.UUID) -> tuple[bool, tuple[int, int, int]]:
    """Re-read a story in a fresh session. Returns (still_duplicated, lengths)."""
    async with async_session_factory() as session:
        story = (
            await session.execute(select(Story).where(Story.id == story_id))
        ).scalar_one_or_none()
        if story is None or story.one_line_summary is None:
            return True, (0, 0, 0)
        lengths = (
            len(story.one_line_summary),
            len(story.short_summary or ""),
            len(story.detailed_summary or ""),
        )
        duplicated = (
            story.one_line_summary == story.short_summary
            and story.short_summary == story.detailed_summary
        )
        return duplicated, lengths


async def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--execute",
        action="store_true",
        help="actually re-synthesise; without this the script only reports",
    )
    parser.add_argument("--limit", type=int, default=50, help="maximum stories to process")
    args = parser.parse_args()

    async with async_session_factory() as session:
        stories = await find_duplicates(session, args.limit)
        targets = [(s.id, len(s.one_line_summary or "")) for s in stories]

    if not targets:
        logger.info("No stories with duplicated summaries. Nothing to do.")
        return

    logger.info("Found %d story(ies) with all three summaries identical:", len(targets))
    for story_id, length in targets:
        logger.info("  %s  %d chars in all three fields", story_id, length)

    if not args.execute:
        logger.info("Dry run. Re-run with --execute to re-synthesise these stories.")
        return

    # A fresh session per story: one synthesis failure must not roll back the
    # stories that already succeeded.
    from app.services.story_synthesis_service import story_synthesis_orchestrator

    repaired = 0
    for story_id, _ in targets:
        try:
            async with async_session_factory() as session:
                await story_synthesis_orchestrator.synthesize_story(
                    session=session,
                    story_id=story_id,
                    trigger="summary_repair",
                )
                await session.commit()
        except Exception:
            logger.exception("Synthesis failed for story %s; leaving it unchanged", story_id)
            continue

        still_duplicated, lengths = await verify(story_id)
        if still_duplicated:
            logger.error("  %s STILL DUPLICATED after re-synthesis (%d/%d/%d)", story_id, *lengths)
        else:
            repaired += 1
            logger.info("  %s repaired: one_line=%d short=%d detailed=%d", story_id, *lengths)

    logger.info("Repaired %d of %d story(ies).", repaired, len(targets))


if __name__ == "__main__":
    asyncio.run(main())

"""Rebuild the Meilisearch `stories` index from Postgres.

Why this exists
---------------
Meilisearch keeps its index on a local Docker volume, while the stories live in
Postgres (Neon). Lose the volume — a new VM, a wiped disk — and Meilisearch
comes back healthy but empty.

Empty-but-healthy is worse than absent. `GET /stories/search` only falls back
to Postgres when Meilisearch is *unreachable*; when it answers with zero hits
the endpoint returns `[]`. So after a migration every search returns nothing
until the index is rebuilt, and nothing reports an error.

The pipeline indexes a story only when clustering touches it, so without this
the index would refill one story at a time, over weeks, and never for stories
that are no longer updated.

What it does
------------
Reads every story with a headline, builds each document with the same
`build_story_document` the pipeline uses (public tags only — `fact:` tags are
excluded exactly as at write time), and adds them in batches. Adding is an
upsert keyed on story id, so re-running is safe.

Usage
-----
    python -m app.scripts.reindex_search              # dry run: counts only
    python -m app.scripts.reindex_search --execute
    python -m app.scripts.reindex_search --execute --batch-size 250
"""

from __future__ import annotations

import argparse
import asyncio
import logging

from sqlalchemy import func, select
from sqlalchemy.orm import selectinload

from app.core.database import async_session_factory
from app.models.models import Story
from app.services.search_service import INDEX_NAME, build_story_document, search_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reindex_search")


def document_for(story: Story) -> dict:
    """The document the pipeline would have written for this story."""
    category_slug = story.category.slug if story.category else None
    tags = [t.tag_name for t in story.tags] if story.tags else []
    public_tags = [t for t in tags if not t.startswith("fact:")]
    return build_story_document(story, category_slug, public_tags)


async def run(execute: bool, batch_size: int) -> None:
    eligible = Story.headline.isnot(None)

    async with async_session_factory() as session:
        total = (await session.execute(select(func.count()).where(eligible))).scalar_one()
    logger.info("stories eligible for indexing: %d", total)

    if not search_service.enabled:
        raise SystemExit("Meilisearch is not configured (MEILISEARCH_URL is empty).")

    if not execute:
        logger.info("DRY RUN — nothing indexed. Re-run with --execute.")
        return

    await search_service.init_index()
    index = search_service._client.index(INDEX_NAME)

    indexed, last_id = 0, None
    while True:
        async with async_session_factory() as session:
            stmt = (
                select(Story)
                .options(selectinload(Story.category), selectinload(Story.tags))
                .where(eligible)
                .order_by(Story.id)
                .limit(batch_size)
            )
            # Keyset pagination: stable under concurrent inserts, unlike OFFSET.
            if last_id is not None:
                stmt = stmt.where(Story.id > last_id)
            batch = list((await session.execute(stmt)).scalars().all())

        if not batch:
            break

        await index.add_documents([document_for(s) for s in batch], primary_key="id")
        indexed += len(batch)
        last_id = batch[-1].id
        logger.info("indexed %d / %d", indexed, total)

    # add_documents is asynchronous inside Meilisearch; report what it holds
    # once the queue drains, so a silent task failure is visible here.
    await asyncio.sleep(2)
    stats = await index.get_stats()
    logger.info(
        "done: sent %d documents; index now reports %d (still indexing: %s)",
        indexed,
        stats.number_of_documents,
        stats.is_indexing,
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--execute", action="store_true", help="actually write to Meilisearch")
    parser.add_argument("--batch-size", type=int, default=500)
    args = parser.parse_args()
    asyncio.run(run(args.execute, args.batch_size))


if __name__ == "__main__":
    main()

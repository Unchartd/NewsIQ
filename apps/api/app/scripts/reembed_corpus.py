"""Migrate the Qdrant corpus to a new embedding model.

Why this exists
---------------
Embedding vectors are only comparable within one model. Measured on candidate
models, the SAME sentence embedded by all-mpnet-base-v2 vs qwen3-embedding-8b
scores cosine 0.02, while two DIFFERENT paraphrases within one model score
0.84-0.92 — and Stage B matches at ~0.67. So changing settings.EMBEDDING_MODEL
does not "upgrade" the corpus; it partitions it into two mutually invisible
halves. New articles could never match any pre-existing story.

VectorService refuses to write a second model's vectors into the collection
for that reason. This script performs the migration properly: drop the
collection, then re-embed every article with the currently configured model.

Cost
----
One embedding call per article. Estimate before running with --dry-run, which
reports the article count and the configured model without calling anything.

Usage
-----
    python -m app.scripts.reembed_corpus --dry-run
    python -m app.scripts.reembed_corpus --execute
    python -m app.scripts.reembed_corpus --execute --batch-size 100 --limit 500
"""

import argparse
import asyncio
import logging

from sqlalchemy import select, text

from app.core.config import settings
from app.core.database import async_session_factory
from app.models.models import Article
from app.services.embedding_service import embedding_service
from app.services.vector_service import COLLECTION_NAME, vector_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reembed_corpus")


async def run(execute: bool, batch_size: int, limit: int | None) -> None:
    model = settings.EMBEDDING_MODEL
    provider = settings.EMBEDDING_PROVIDER

    async with async_session_factory() as session:
        total = (
            await session.execute(
                text("SELECT count(*) FROM articles WHERE embedding_status = 'completed'")
            )
        ).scalar() or 0

    logger.info("target embedding model : %s (provider=%s)", model, provider)
    logger.info("articles to re-embed   : %s", total)

    if not execute:
        logger.info(
            "DRY RUN — nothing changed. This will drop the '%s' collection and issue "
            "%s embedding calls. Re-run with --execute.",
            COLLECTION_NAME,
            total,
        )
        return

    # Drop the collection: its vectors belong to the previous model's space and
    # cannot be mixed with, or compared against, the new ones.
    logger.warning("Dropping Qdrant collection '%s' …", COLLECTION_NAME)
    try:
        await vector_service.client.delete_collection(collection_name=COLLECTION_NAME)
    except Exception as exc:
        logger.warning("Collection drop reported: %s (continuing)", exc)
    vector_service._collection_ready = False
    vector_service._space_checked = False
    await vector_service.init_collection()

    done = 0
    failed = 0
    offset = 0

    while True:
        async with async_session_factory() as session:
            stmt = (
                select(Article)
                .where(Article.embedding_status == "completed")
                .order_by(Article.created_at.desc())
                .offset(offset)
                .limit(batch_size)
            )
            batch = list((await session.execute(stmt)).scalars().all())

        if not batch:
            break

        for article in batch:
            parts = [
                article.title or "",
                article.description or "",
                (article.content or "")[:4000],
            ]
            body = " ".join(p for p in parts if p).strip() or "Empty news article"
            try:
                vector = await embedding_service.get_embedding(body)
                await vector_service.upsert_article(
                    article_id=article.id,
                    vector=vector,
                    payload={
                        "title": article.title,
                        "url": article.url,
                        "source_id": str(article.source_id),
                        "published_at": article.published_at.isoformat()
                        if article.published_at
                        else None,
                        "embedding_model": model,
                        "embedding_dim": len(vector),
                    },
                )
                done += 1
            except Exception as exc:
                failed += 1
                logger.error("Re-embed failed for article %s: %s", article.id, exc)

        offset += len(batch)
        logger.info("progress: %s re-embedded, %s failed", done, failed)
        if limit is not None and offset >= limit:
            logger.info("Reached --limit %s, stopping.", limit)
            break

    logger.info("Re-embed complete: %s succeeded, %s failed.", done, failed)
    if failed:
        logger.warning(
            "%s articles have no vector and cannot cluster until re-embedded. "
            "Re-run this script to retry them.",
            failed,
        )
    await vector_service.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--execute", action="store_true", help="Apply (default: dry run).")
    parser.add_argument("--batch-size", type=int, default=50)
    parser.add_argument("--limit", type=int, default=None, help="Stop after N articles.")
    args = parser.parse_args()
    asyncio.run(run(args.execute, args.batch_size, args.limit))


if __name__ == "__main__":
    main()

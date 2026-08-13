"""Merge existing stories that describe the same event.

Why this is needed
------------------
Clustering only ever evaluates an article once — at extraction time, against
the stories that existed at that moment. Articles that arrive in different
batches, or that were processed while clustering was broken, become separate
stories and are never reconsidered. Nothing in the pipeline re-examines an
already-clustered article.

So every defect that suppressed merging left permanent fragmentation behind:
the Stage A anchor deadlock (score ceiling 44.5 against a threshold of 45) and
story centroids stranded in a previous embedding model's vector space (article
cosine 0.95 against its own stale centroid: 0.02). Both are fixed forward, but
the stories they split stay split.

This performs the comparison that never happened, using the SAME validators
production uses — no bespoke similarity logic, so a merge here means exactly
what a merge means in the live path.

Safety
------
* Dry run by default; --execute is required to write.
* Only merges when Stage A passes AND Stage B passes, the same bar as the
  live incremental path.
* Merges the smaller story into the larger (ties: older wins), so article
  history and the canonical story id are preserved.
* Re-checks membership before writing, so a story that was merged earlier in
  the same run is never processed twice.

Usage
-----
    python -m app.scripts.reconcile_duplicate_stories
    python -m app.scripts.reconcile_duplicate_stories --execute
    python -m app.scripts.reconcile_duplicate_stories --hours 168 --execute
"""

import argparse
import asyncio
import logging
from datetime import UTC, datetime, timedelta

import numpy as np
from sqlalchemy import delete, select, text

from app.core.database import async_session_factory
from app.models.models import (
    Article,
    ArticleEntity,
    Story,
    StoryArticle,
    StoryEntity,
)
from app.services.event_validation_service import StoryAnchor, event_validation_service
from app.services.vector_service import vector_service

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("reconcile")

# Cheap pre-filter before running the real validators. Well below Stage B's
# threshold so it cannot mask a decision the validators would have made.
CENTROID_PREFILTER = 0.60

# Derived per-story rows: safe to drop on merge because synthesis rebuilds them
# for the surviving story. User-owned rows (bookmarks, user_events) are NOT
# here — they are repointed, since deleting them would destroy someone's saved
# story to tidy up a clustering mistake.
_DERIVED_CHILD_TABLES = (
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
    "story_articles",
)


def _cos(a: list[float] | None, b: list[float] | None) -> float:
    if not a or not b:
        return 0.0
    va, vb = np.asarray(a, dtype=float), np.asarray(b, dtype=float)
    na, nb = float(np.linalg.norm(va)), float(np.linalg.norm(vb))
    if na == 0.0 or nb == 0.0:
        return 0.0
    return float(va @ vb / (na * nb))


async def _anchor_for(story: Story, session) -> StoryAnchor:
    rows = (
        await session.execute(
            select(StoryEntity.entity_value, StoryEntity.entity_type).where(
                StoryEntity.story_id == story.id
            )
        )
    ).all()
    now = datetime.now(UTC).replace(tzinfo=None)
    return StoryAnchor(
        story_id=str(story.id),
        headline=story.headline or "",
        first_seen_at=story.first_seen_at or now,
        last_updated_at=story.updated_at or now,
        primary_entities={v.lower() for v, _ in rows if v},
        top_locations={v.lower() for v, t in rows if v and t in ("GPE", "LOC")},
        category=None,
        event_type=None,
        centroid_vector=story.story_embedding,
        entity_graph_ids=set(),
    )


async def run(hours: int, execute: bool) -> None:
    cutoff = datetime.now(UTC).replace(tzinfo=None) - timedelta(hours=hours)

    async with async_session_factory() as session:
        stories = list(
            (
                await session.execute(
                    select(Story)
                    .where(Story.created_at >= cutoff, Story.story_embedding.isnot(None))
                    .order_by(Story.created_at.asc())
                )
            )
            .scalars()
            .all()
        )
        sizes = {}
        for (sid,) in (
            await session.execute(select(Story.id).where(Story.created_at >= cutoff))
        ).all():
            sizes[sid] = (
                (
                    await session.execute(
                        select(StoryArticle.article_id).where(StoryArticle.story_id == sid)
                    )
                )
                .scalars()
                .all()
            )

    logger.info("Examining %d stories created in the last %dh", len(stories), hours)

    absorbed: set = set()
    merges: list[tuple[Story, Story, float, float]] = []

    for i, story_a in enumerate(stories):
        if story_a.id in absorbed:
            continue
        for story_b in stories[i + 1 :]:
            if story_b.id in absorbed:
                continue
            pre = _cos(story_a.story_embedding, story_b.story_embedding)
            if pre < CENTROID_PREFILTER:
                continue

            # Keep the larger story; ties resolve to the older one.
            a_n, b_n = len(sizes.get(story_a.id, [])), len(sizes.get(story_b.id, []))
            keep, drop = (story_a, story_b) if a_n >= b_n else (story_b, story_a)

            async with async_session_factory() as session:
                drop_articles = sizes.get(drop.id, [])
                if not drop_articles:
                    continue
                article = (
                    await session.execute(select(Article).where(Article.id == drop_articles[0]))
                ).scalar_one_or_none()
                if article is None:
                    continue
                art_ents = set(
                    (
                        await session.execute(
                            select(ArticleEntity.entity_value).where(
                                ArticleEntity.article_id == article.id
                            )
                        )
                    )
                    .scalars()
                    .all()
                )
                anchor = await _anchor_for(keep, session)

            decision_a = event_validation_service.validate_stage_a(
                article, anchor, article_entities=art_ents
            )
            if decision_a.outcome.value == "FAIL":
                continue

            vecs = await vector_service.retrieve_vectors([str(article.id)])
            if not vecs:
                continue
            decision_b = event_validation_service.validate_stage_b(
                article, anchor, list(vecs.values())[0], set()
            )
            if decision_b.outcome.value != "PASS":
                continue

            merges.append((keep, drop, decision_a.score, decision_b.score))
            absorbed.add(drop.id)
            logger.info(
                "MERGE  %s <- %s  (stageA %.1f, stageB %.3f)\n        keep: %s\n        drop: %s",
                str(keep.id)[:8],
                str(drop.id)[:8],
                decision_a.score,
                decision_b.score,
                (keep.headline or "")[:70],
                (drop.headline or "")[:70],
            )

    logger.info("%d merge(s) identified", len(merges))
    if not execute:
        logger.info("DRY RUN — nothing changed. Re-run with --execute to apply.")
        return

    applied = 0
    for keep, drop, _, _ in merges:
        async with async_session_factory() as session:
            try:
                keep_ids = set(
                    (
                        await session.execute(
                            select(StoryArticle.article_id).where(StoryArticle.story_id == keep.id)
                        )
                    )
                    .scalars()
                    .all()
                )
                move = [
                    a
                    for a in (
                        await session.execute(
                            select(StoryArticle.article_id).where(StoryArticle.story_id == drop.id)
                        )
                    )
                    .scalars()
                    .all()
                    if a not in keep_ids
                ]
                for aid in move:
                    session.add(StoryArticle(story_id=keep.id, article_id=aid))

                # A merge is not a purge. Rows representing a USER's relationship
                # to the story are repointed at the survivor; derived rows are
                # dropped because synthesis regenerates them.
                #
                # Every table with a FK to stories.id must be handled or the
                # DELETE fails — story_metrics alone exists for every story, so
                # an earlier version of this would have errored on all 41 merges.
                for tbl, user_col in (("bookmarks", "user_id"), ("user_events", "user_id")):
                    # Drop only where the user already holds the survivor (that
                    # pair is unique); repoint everything else.
                    await session.execute(
                        text(
                            f"DELETE FROM {tbl} WHERE story_id = :drop AND {user_col} IN "  # noqa: S608
                            f"(SELECT {user_col} FROM {tbl} WHERE story_id = :keep)"
                        ),
                        {"drop": drop.id, "keep": keep.id},
                    )
                    await session.execute(
                        text(f"UPDATE {tbl} SET story_id = :keep WHERE story_id = :drop"),  # noqa: S608
                        {"drop": drop.id, "keep": keep.id},
                    )

                # Break the circular FK before deleting story_versions.
                await session.execute(
                    text("UPDATE stories SET current_version_id = NULL WHERE id = :d"),
                    {"d": drop.id},
                )
                await session.execute(
                    text("UPDATE story_candidates SET story_id = NULL WHERE story_id = :d"),
                    {"d": drop.id},
                )
                for tbl in _DERIVED_CHILD_TABLES:
                    await session.execute(
                        text(f"DELETE FROM {tbl} WHERE story_id = :d"),  # noqa: S608
                        {"d": drop.id},
                    )
                await session.execute(delete(Story).where(Story.id == drop.id))
                await session.commit()
                applied += 1
            except Exception as exc:
                await session.rollback()
                logger.error("Merge %s <- %s failed: %s", keep.id, drop.id, exc)

    # Centroids and anchors must reflect the new membership.
    from app.services.clustering_service import clustering_service

    for keep, _, _, _ in merges:
        async with async_session_factory() as session:
            story = (
                await session.execute(select(Story).where(Story.id == keep.id))
            ).scalar_one_or_none()
            if story is None:
                continue
            members = (
                (
                    await session.execute(
                        select(StoryArticle.article_id).where(StoryArticle.story_id == keep.id)
                    )
                )
                .scalars()
                .all()
            )
            try:
                await clustering_service.refresh_story_centroid(
                    story, session, article_ids=list(members)
                )
                await clustering_service.seed_story_anchor(story, list(members), session)
                await session.commit()
            except Exception as exc:
                await session.rollback()
                logger.error("Post-merge refresh failed for %s: %s", keep.id, exc)

    logger.info("Applied %d merge(s).", applied)
    await vector_service.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--hours", type=int, default=72, help="Story age window (default: 72).")
    parser.add_argument("--execute", action="store_true", help="Apply (default: dry run).")
    parser.add_argument("--dry-run", action="store_true", help="Report only (the default).")
    args = parser.parse_args()
    asyncio.run(run(args.hours, args.execute and not args.dry_run))


if __name__ == "__main__":
    main()

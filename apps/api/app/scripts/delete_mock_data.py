import asyncio
import sys

from sqlalchemy import delete, select

from app.core.database import async_session_factory
from app.models.models import (
    Article,
    Story,
    StoryArticle,
    StoryContradiction,
    StoryDifference,
    StorySourceCoverage,
)

# Set utf-8 output to prevent windows encoding crash
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")


async def main():
    async with async_session_factory() as session:
        # 1. Delete mock differences
        stmt_diff = select(StoryDifference)
        res_diff = await session.execute(stmt_diff)
        diffs = res_diff.scalars().all()
        diffs_deleted = 0
        for d in diffs:
            if any(
                x and ("[Mock]" in x or "mock" in x.lower())
                for x in [d.unique_information, d.missing_information, d.contradictions]
            ):
                await session.execute(delete(StoryDifference).where(StoryDifference.id == d.id))
                diffs_deleted += 1
        print(f"Deleted {diffs_deleted} mock StoryDifference rows.")

        # 2. Delete mock coverages
        stmt_cov = select(StorySourceCoverage)
        res_cov = await session.execute(stmt_cov)
        covs = res_cov.scalars().all()
        covs_deleted = 0
        for c in covs:
            if any(x and ("[Mock]" in x or "mock" in x.lower()) for x in [c.focus_area]):
                await session.execute(
                    delete(StorySourceCoverage).where(StorySourceCoverage.id == c.id)
                )
                covs_deleted += 1
        print(f"Deleted {covs_deleted} mock StorySourceCoverage rows.")

        # 3. Delete mock contradictions
        stmt_contra = select(StoryContradiction)
        res_contra = await session.execute(stmt_contra)
        contras = res_contra.scalars().all()
        contras_deleted = 0
        for ct in contras:
            if any(x and ("[Mock]" in x or "mock" in x.lower()) for x in [ct.description]):
                await session.execute(
                    delete(StoryContradiction).where(StoryContradiction.id == ct.id)
                )
                contras_deleted += 1
        print(f"Deleted {contras_deleted} mock StoryContradiction rows.")

        # 4. Clean up mock stories
        stmt_story = select(Story)
        res_story = await session.execute(stmt_story)
        stories = res_story.scalars().all()
        stories_deleted = 0
        stories_repaired = 0
        for s in stories:
            # If the headline or summaries contain "[Mock]", we either repair them or delete them.
            # If it's a completely fake story, we delete it. Let's check if the headline starts with "[Mock]".
            is_mock_event = s.headline and (
                s.headline.startswith("[Mock]") or s.headline == "Major News Event"
            )
            if is_mock_event:
                # Check if it has real articles. If no articles, or if it's a completely mock story, delete it.
                stmt_art = select(StoryArticle).where(StoryArticle.story_id == s.id)
                res_art = await session.execute(stmt_art)
                arts = res_art.scalars().all()
                if not arts or s.headline == "[Mock] Major News Event":
                    # Delete dependencies first
                    from app.models.models import (
                        StoryEntity,
                        StoryMetric,
                        StoryTag,
                        StoryTimelineEvent,
                    )

                    await session.execute(delete(StoryTag).where(StoryTag.story_id == s.id))
                    await session.execute(delete(StoryEntity).where(StoryEntity.story_id == s.id))
                    await session.execute(delete(StoryMetric).where(StoryMetric.story_id == s.id))
                    await session.execute(
                        delete(StoryTimelineEvent).where(StoryTimelineEvent.story_id == s.id)
                    )
                    await session.execute(delete(StoryArticle).where(StoryArticle.story_id == s.id))
                    await session.execute(
                        delete(StoryDifference).where(StoryDifference.story_id == s.id)
                    )
                    await session.execute(
                        delete(StorySourceCoverage).where(StorySourceCoverage.story_id == s.id)
                    )
                    await session.execute(
                        delete(StoryContradiction).where(StoryContradiction.story_id == s.id)
                    )

                    # Delete the story itself
                    await session.execute(delete(Story).where(Story.id == s.id))
                    stories_deleted += 1
                    continue

            # If the story summaries contain "[Mock]" or "Factual Synthesis", we repair them using the first article's content!
            has_mock = any(
                x and ("[Mock]" in x or "mock" in x.lower() or "factual synthesis" in x.lower())
                for x in [s.headline, s.one_line_summary, s.short_summary, s.detailed_summary]
            )
            if has_mock:
                # Fetch articles
                stmt_art = (
                    select(Article)
                    .join(StoryArticle, StoryArticle.article_id == Article.id)
                    .where(StoryArticle.story_id == s.id)
                )
                res_art = await session.execute(stmt_art)
                articles = res_art.scalars().all()
                if articles:
                    primary_title = articles[0].title or "News Story"
                    primary_desc = (
                        articles[0].description
                        or articles[0].content[:200]
                        or "Summary currently unavailable."
                    )

                    s.headline = primary_title
                    s.one_line_summary = primary_desc
                    s.short_summary = primary_desc
                    s.detailed_summary = primary_desc
                    session.add(s)
                    stories_repaired += 1

        await session.commit()
        print(f"Deleted {stories_deleted} mock stories.")
        print(f"Repaired {stories_repaired} stories with mock or fallback summaries.")


if __name__ == "__main__":
    asyncio.run(main())

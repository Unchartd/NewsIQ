import asyncio
import sys
from sqlalchemy import select, delete, update
from app.core.database import async_session_factory
from app.models.models import (
    Article,
    ArticleEvent,
    Story,
    StoryArticle,
    StoryTag,
    StoryEntity,
    StoryMetric,
    StoryTimelineEvent,
    StoryDifference,
    StorySourceCoverage,
    StoryContradiction,
    Bookmark,
    UserEvent,
)

# Set utf-8 output to prevent windows encoding crash
sys.stdout.reconfigure(encoding='utf-8')

async def main():
    async with async_session_factory() as session:
        # 1. Identify mock article events
        stmt_evts = select(ArticleEvent)
        res_evts = await session.execute(stmt_evts)
        events = res_evts.scalars().all()
        
        mock_event_ids = []
        mock_article_ids = set()
        
        for e in events:
            is_mock = False
            if e.location == "Mock location":
                is_mock = True
            if e.actors and any("Mock bullet point" in str(act) for act in e.actors):
                is_mock = True
            if e.targets and any("Mock bullet point" in str(t) for t in e.targets):
                is_mock = True
            if e.event_fingerprint == "ed3d6de9f781eb537227b79560b67388":
                is_mock = True
                
            if is_mock:
                mock_event_ids.append(e.id)
                mock_article_ids.add(e.article_id)
                
        print(f"Found {len(mock_event_ids)} mock ArticleEvent rows affecting {len(mock_article_ids)} articles.")
        
        # Delete mock ArticleEvent rows
        if mock_event_ids:
            await session.execute(delete(ArticleEvent).where(ArticleEvent.id.in_(mock_event_ids)))
            print(f"Deleted {len(mock_event_ids)} mock ArticleEvent rows.")
            
        # Reset event extraction status for affected articles
        if mock_article_ids:
            await session.execute(
                update(Article)
                .where(Article.id.in_(list(mock_article_ids)))
                .values(event_extraction_status="pending")
            )
            print(f"Reset event_extraction_status to 'pending' for {len(mock_article_ids)} articles.")

        # 2. Delete ALL stories and child tables to clear wrong merges
        print("Truncating Story tables and dependencies...")
        from sqlalchemy import text
        
        # Count original stories
        stmt_stories_count = select(Story)
        res_stories_count = await session.execute(stmt_stories_count)
        stories_count = len(res_stories_count.scalars().all())
        
        # Truncate tables using CASCADE
        await session.execute(text(
            "TRUNCATE TABLE story_metrics, story_timeline_events, story_source_coverage, "
            "story_differences, story_contradictions, story_tags, story_entities, "
            "story_articles, bookmarks, user_events, stories CASCADE;"
        ))
        
        await session.commit()
        print(f"Successfully deleted {stories_count} stories and all their dependencies.")
        print("Database has been reset of all mock data and merged stories.")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.core.database import async_session_factory
from app.models.models import Article, DiscoveryTask, CrawlTask, Story, StoryArticle, StoryEntity, Source

async def main():
    print("=== NewsIQ Ingestion & Discovery Pipeline Funnel Analysis (Historical / All-time) ===")
    
    async with async_session_factory() as session:
        # 1. Total RSS articles processed
        discovery_subq = select(CrawlTask.article_id).where(CrawlTask.article_id.is_not(None))
        rss_articles_stmt = select(func.count(Article.id)).where(
            ~Article.id.in_(discovery_subq)
        )
        rss_count = (await session.execute(rss_articles_stmt)).scalar()
        print(f"1. Total RSS Articles Ingested (All-time): {rss_count}")
        
        # 2. Discovery Tasks
        total_tasks_stmt = select(func.count(DiscoveryTask.id))
        total_tasks = (await session.execute(total_tasks_stmt)).scalar()
        print(f"2. Total Discovery Tasks (All-time): {total_tasks}")
        
        # Breakdown by status
        statuses_stmt = select(DiscoveryTask.status, func.count(DiscoveryTask.id)).group_by(DiscoveryTask.status)
        statuses = (await session.execute(statuses_stmt)).all()
        print(f"   Breakdown of Discovery Tasks by Status:")
        for status, count in statuses:
            print(f"     - {status}: {count}")
            
        # 3. Total Crawl Tasks
        crawltasks_count_stmt = select(func.count(CrawlTask.id))
        total_crawltasks = (await session.execute(crawltasks_count_stmt)).scalar()
        print(f"3. Total Crawl Tasks (URLs found) (All-time): {total_crawltasks}")
        
        # 4. Crawl Tasks status breakdown
        crawltask_statuses_stmt = select(CrawlTask.status, CrawlTask.outcome, func.count(CrawlTask.id)).group_by(CrawlTask.status, CrawlTask.outcome)
        crawltask_statuses = (await session.execute(crawltask_statuses_stmt)).all()
        print(f"4. Crawl Tasks status breakdown:")
        for status, outcome, count in crawltask_statuses:
            print(f"     - Status: {status}, Outcome: {outcome}: {count}")
            
        # 5. Discovery Articles Persisted
        persisted_stmt = select(func.count(Article.id)).where(
            Article.id.in_(discovery_subq)
        )
        persisted_count = (await session.execute(persisted_stmt)).scalar()
        print(f"5. Total Discovery Articles Persisted (All-time): {persisted_count}")
        
        # 6. Overall story/cluster statistics
        total_stories = (await session.execute(select(func.count(Story.id)))).scalar()
        print(f"\n6. Total Stories (All-time): {total_stories}")
        
        # Multi-source clusters
        multi_source_count = 0
        stories_stmt = select(Story).options(selectinload(Story.articles).selectinload(StoryArticle.article))
        stories = (await session.execute(stories_stmt)).scalars().all()
        
        source_counts = []
        for s in stories:
            sources = {a.article.source_id for a in s.articles if a.article and a.article.source_id}
            source_counts.append(len(sources))
            if len(sources) >= 2:
                multi_source_count += 1
                
        avg_sources = sum(source_counts) / len(source_counts) if source_counts else 0.0
        print(f"7. Total Multi-source Clusters: {multi_source_count}")
        print(f"8. Average Unique Sources per Story: {avg_sources:.2f}")

if __name__ == "__main__":
    asyncio.run(main())

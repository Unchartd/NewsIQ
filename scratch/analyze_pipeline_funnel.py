import asyncio
from datetime import datetime, UTC
from sqlalchemy import select, func, or_
from sqlalchemy.orm import selectinload
from app.core.database import async_session_factory
from app.models.models import Article, DiscoveryTask, CrawlTask, Story, StoryArticle, StoryEntity, Source

async def main():
    print("=== NewsIQ Ingestion & Discovery Pipeline Funnel Analysis ===")
    
    async with async_session_factory() as session:
        # 1. Total RSS articles processed today
        # Since today is July 14, 2026, let's filter by created_at >= July 14, 2026
        today = datetime(2026, 7, 14, 0, 0, 0)
        
        # We can find all articles where source is an RSS source (not discovery).
        # How do we know if it is an RSS source? Discovery tasks produce CrawlTasks with a persisted_article.
        # So discovery articles are referenced by CrawlTask.article_id.
        discovery_subq = select(CrawlTask.article_id).where(CrawlTask.article_id.is_not(None))
        rss_articles_stmt = select(func.count(Article.id)).where(
            Article.created_at >= today,
            ~Article.id.in_(discovery_subq)
        )
        rss_count = (await session.execute(rss_articles_stmt)).scalar()
        print(f"1. RSS Articles Ingested Today: {rss_count}")
        
        # 2. Discovery Tasks (Google News RSS search)
        total_tasks_stmt = select(func.count(DiscoveryTask.id)).where(DiscoveryTask.created_at >= today)
        total_tasks = (await session.execute(total_tasks_stmt)).scalar()
        print(f"2. Discovery Tasks Created Today (searches triggered): {total_tasks}")
        
        # Breakdown by status
        statuses_stmt = select(DiscoveryTask.status, func.count(DiscoveryTask.id)).where(DiscoveryTask.created_at >= today).group_by(DiscoveryTask.status)
        statuses = (await session.execute(statuses_stmt)).all()
        print(f"   Breakdown of Discovery Tasks by Status:")
        for status, count in statuses:
            print(f"     - {status}: {count}")
            
        # 3. Searches that returned results
        # A task succeeded if status is complete, urls_found, or crawling.
        # Let's count URLs returned per search
        crawltasks_count_stmt = select(func.count(CrawlTask.id)).where(CrawlTask.created_at >= today)
        total_crawltasks = (await session.execute(crawltasks_count_stmt)).scalar()
        print(f"3. Total Crawl Tasks (URLs found) Today: {total_crawltasks}")
        
        # 4. URLs skipped vs crawled vs persisted
        crawltask_statuses_stmt = select(CrawlTask.status, CrawlTask.outcome, func.count(CrawlTask.id)).where(CrawlTask.created_at >= today).group_by(CrawlTask.status, CrawlTask.outcome)
        crawltask_statuses = (await session.execute(crawltask_statuses_stmt)).all()
        print(f"4. Crawl Tasks status breakdown:")
        for status, outcome, count in crawltask_statuses:
            print(f"     - Status: {status}, Outcome: {outcome}: {count}")
            
        # 5. Persisted discovery articles
        persisted_stmt = select(func.count(Article.id)).where(
            Article.created_at >= today,
            Article.id.in_(discovery_subq)
        )
        persisted_count = (await session.execute(persisted_stmt)).scalar()
        print(f"5. Discovery Articles Persisted Today: {persisted_count}")
        
        # Let's print out the exact audit trail for all discovery tasks created today!
        print("\n=== Audit Trail for Discovered Articles ===")
        # Get tasks with their original articles and crawl tasks
        tasks_stmt = (
            select(DiscoveryTask)
            .options(selectinload(DiscoveryTask.article), selectinload(DiscoveryTask.crawl_tasks).selectinload(CrawlTask.persisted_article))
            .where(DiscoveryTask.created_at >= today)
            .order_by(DiscoveryTask.created_at.desc())
        )
        tasks = (await session.execute(tasks_stmt)).scalars().all()
        
        for t in tasks:
            orig_art = t.article
            print(f"RSS Article: {orig_art.title if orig_art else 'Unknown'}")
            print(f"  URL: {orig_art.url if orig_art else 'Unknown'}")
            print(f"  Normalized Headline: {t.query}")
            print(f"  Google News RSS Query: {t.query}")
            print(f"  Status: {t.status}")
            print(f"  Returned URLs:")
            for ct in t.crawl_tasks:
                print(f"    - URL: {ct.url}")
                print(f"      Status: {ct.status}, Outcome: {ct.outcome}")
                if ct.persisted_article:
                    pa = ct.persisted_article
                    print(f"      Persisted Article Title: {pa.title}")
                    # Check if it has been clustered
                    sa_stmt = select(StoryArticle).where(StoryArticle.article_id == pa.id)
                    sa = (await session.execute(sa_stmt)).scalar_one_or_none()
                    if sa:
                        # Fetch story
                        st_stmt = select(Story).where(Story.id == sa.story_id)
                        st = (await session.execute(st_stmt)).scalar_one_or_none()
                        print(f"      Final Story ID: {st.id if st else 'Unknown'} (Headline: {st.headline if st else 'None'})")
                        print(f"      Story Status: {st.story_status if st else 'Unknown'}")
                    else:
                        print(f"      Final Story ID: Not Clustered")
            print("-" * 60)
            
        # 6. Overall story/cluster statistics for today
        total_stories_today = (await session.execute(select(func.count(Story.id)).where(Story.created_at >= today))).scalar()
        print(f"\n6. Total Stories Created Today: {total_stories_today}")
        
        # Multi-source clusters today
        # A story is multi-source if it has articles from different sources
        multi_source_count = 0
        stories_today_stmt = select(Story).where(Story.created_at >= today).options(selectinload(Story.articles).selectinload(StoryArticle.article))
        stories_today = (await session.execute(stories_today_stmt)).scalars().all()
        
        source_counts = []
        for s in stories_today:
            sources = {a.article.source_id for a in s.articles if a.article and a.article.source_id}
            source_counts.append(len(sources))
            if len(sources) >= 2:
                multi_source_count += 1
                
        avg_sources = sum(source_counts) / len(source_counts) if source_counts else 0.0
        print(f"7. Multi-source Clusters Created Today: {multi_source_count}")
        print(f"8. Average Unique Sources per Story Created Today: {avg_sources:.2f}")

if __name__ == "__main__":
    asyncio.run(main())

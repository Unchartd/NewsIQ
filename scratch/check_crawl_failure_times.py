import asyncio
from sqlalchemy import select, func
from app.core.database import async_session_factory
from app.models.models import CrawlTask

async def main():
    print("=== Crawl Task Failures Grouped by Date ===")
    async with async_session_factory() as session:
        stmt = (
            select(func.date(CrawlTask.created_at), func.count(CrawlTask.id))
            .where(CrawlTask.outcome == "FAILED")
            .group_by(func.date(CrawlTask.created_at))
            .order_by(func.date(CrawlTask.created_at).desc())
        )
        results = (await session.execute(stmt)).all()
        for date_val, count in results:
            print(f"Date: {date_val} - Failed count: {count}")

if __name__ == "__main__":
    asyncio.run(main())

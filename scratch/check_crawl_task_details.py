import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.models import CrawlTask

async def main():
    print("=== Last 15 Crawl Tasks ===")
    async with async_session_factory() as session:
        stmt = (
            select(CrawlTask)
            .where(CrawlTask.outcome == "FAILED")
            .order_by(CrawlTask.created_at.desc())
            .limit(15)
        )
        results = (await session.execute(stmt)).scalars().all()
        for ct in results:
            print(f"Created: {ct.created_at.isoformat()} | Status: {ct.status} | Outcome: {ct.outcome} | URL: {ct.url[:80]}... | Error: {str(ct.last_error)[:100]}")

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.models import CrawlTask

async def main():
    print("=== CrawlTask Errors ===")
    async with async_session_factory() as session:
        stmt = select(CrawlTask).where(CrawlTask.last_error.is_not(None)).limit(10)
        res = await session.execute(stmt)
        tasks = res.scalars().all()
        
        for t in tasks:
            print(f"- ID: {t.id}")
            print(f"  URL: {t.url}")
            print(f"  Status: {t.status}, Outcome: {t.outcome}")
            print(f"  Retry count: {t.retry_count}")
            print(f"  Last error: {t.last_error}")
            print("-" * 50)

if __name__ == "__main__":
    asyncio.run(main())

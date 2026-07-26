import asyncio
from sqlalchemy import select, func
from app.core.database import async_session_factory
from app.models.models import CrawlTask

async def main():
    print("=== Diagnosing Production Crawl Errors ===")
    async with async_session_factory() as session:
        # Query failed crawl tasks and count grouped by last_error
        stmt = (
            select(CrawlTask.last_error, func.count(CrawlTask.id))
            .where(CrawlTask.outcome == "FAILED")
            .group_by(CrawlTask.last_error)
            .order_by(func.count(CrawlTask.id).desc())
        )
        results = (await session.execute(stmt)).all()
        
        print(f"Total failed crawl tasks query returned {len(results)} distinct error signatures:\n")
        for err, count in results:
            err_snippet = (err or "None")[:150].replace('\n', ' ')
            print(f"[{count} occurrences] {err_snippet}")

if __name__ == "__main__":
    asyncio.run(main())

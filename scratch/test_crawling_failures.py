import asyncio
import httpx
from sqlalchemy import select
from app.core.database import async_session_factory
from app.models.models import CrawlTask
from app.services.crawler_service import crawler_service

async def main():
    print("=== Testing Crawling Failures ===")
    async with async_session_factory() as session:
        # Fetch 5 failed crawl tasks
        stmt = select(CrawlTask.url).where(CrawlTask.outcome == "FAILED").limit(5)
        urls = (await session.execute(stmt)).scalars().all()
        
        print(f"Selected failed URLs from database: {urls}\n")
        
        for url in urls:
            print("-" * 50)
            print(f"Testing URL: {url}")
            
            # 1. Fetch HTML directly and log status code/headers
            try:
                async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=crawler_service.headers) as client:
                    resp = await client.get(url)
                    print(f"Direct fetch: Status {resp.status_code}")
                    print(f"Response URL: {resp.url}")
                    print(f"Content Length: {len(resp.text)}")
                    print(f"HTML snippet: {resp.text[:200].strip()}")
            except Exception as e:
                print(f"Direct fetch failed: {type(e).__name__} - {e}")
                
            # 2. Run crawler service
            try:
                res = await crawler_service.crawl_article(url)
                if res:
                    print(f"Crawler Service: Success! Extractor: {res.get('extractor')}, text length: {len(res.get('content'))}")
                else:
                    print(f"Crawler Service: Failed (returned None)")
            except Exception as e:
                print(f"Crawler Service failed with exception: {e}")

if __name__ == "__main__":
    asyncio.run(main())

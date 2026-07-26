import asyncio
from app.services.crawler_service import crawler_service

async def main():
    url = "https://www.reuters.com/world/canada-regulator-cited-anthropics-claude-mythos-warning-banks-cyber-risks-email-2026-07-13/"
    print("Testing crawler_service.crawl_article on live Reuters article...")
    result = await crawler_service.crawl_article(url)
    
    print("\n--- Crawl Results ---")
    print(f"Success: {result.get('success')}")
    print(f"Title: {result.get('title')}")
    print(f"Extractor used: {result.get('extractor')}")
    print(f"Content length: {len(result.get('content', '') or '')}")
    print(f"Author: {result.get('author')}")
    print(f"Published At: {result.get('published_at')}")
    print(f"Diagnostics: {result.get('diagnostics')}")
    
    if result.get("success") and result.get("content"):
        print("\nContent snippet:")
        print(result.get("content")[:300].encode('ascii', errors='ignore').decode('ascii'))

if __name__ == "__main__":
    asyncio.run(main())

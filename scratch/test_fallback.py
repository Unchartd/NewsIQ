import asyncio
import httpx
import logging
from curl_cffi.requests import AsyncSession

logger = logging.getLogger(__name__)

async def fetch_html(url: str) -> str | None:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            response = await client.get(url)
            response.raise_for_status()
            return response.text
    except Exception as e:
        print(f"Standard HTTP fetch failed for {url}: {e}. Trying stealth fallback...")
        try:
            async with AsyncSession(impersonate="chrome") as session:
                response = await session.get(url, timeout=15.0)
                response.raise_for_status()
                print("Stealth fallback succeeded!")
                return response.text
        except Exception as fallback_err:
            print(f"Stealth fallback fetch failed for {url}: {fallback_err}")
            return None

async def main():
    url = "https://www.reuters.com/world/canada-regulator-cited-anthropics-claude-mythos-warning-banks-cyber-risks-email-2026-07-13/"
    html = await fetch_html(url)
    if html:
        print(f"Succeeded! Length: {len(html)}")
    else:
        print("Failed entirely.")

if __name__ == "__main__":
    asyncio.run(main())

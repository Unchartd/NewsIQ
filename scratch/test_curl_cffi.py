import asyncio
from curl_cffi.requests import AsyncSession

async def test_url(url):
    print(f"\nTesting URL with curl_cffi: {url}")
    try:
        # We can impersonate a specific browser. "chrome" is default/recommended.
        async with AsyncSession(impersonate="chrome") as session:
            resp = await session.get(url, timeout=15)
            print(f"Status code: {resp.status_code}")
            print(f"Content length: {len(resp.text)}")
            print(f"Snippet: {resp.text[:300].strip()}")
            return resp.status_code == 200
    except Exception as e:
        print(f"Failed to fetch using curl_cffi: {e}")
        return False

async def main():
    urls = [
        "https://www.reuters.com/world/canada-regulator-cited-anthropics-claude-mythos-warning-banks-cyber-risks-email-2026-07-13/",
        "https://www.washingtonpost.com/world/2026/07/14/france-bastille-day-ukraine-troops/"
    ]
    for url in urls:
        await test_url(url)

if __name__ == "__main__":
    asyncio.run(main())

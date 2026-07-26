import asyncio
import httpx

async def test_ua(url, ua):
    headers = {
        "User-Agent": ua,
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers) as client:
            resp = await client.get(url)
            print(f"UA: {ua[:50]}...")
            print(f"  Status: {resp.status_code} | Length: {len(resp.text)}")
            if resp.status_code == 200:
                print(f"  Snippet: {resp.text[:200].strip()}")
            return resp.status_code == 200
    except Exception as e:
        print(f"  Error: {e}")
        return False

async def main():
    url = "https://www.reuters.com/world/canada-regulator-cited-anthropics-claude-mythos-warning-banks-cyber-risks-email-2026-07-13/"
    
    uas = [
        # Googlebot
        "Mozilla/5.0 (compatible; Googlebot/2.1; +http://www.google.com/bot.html)",
        # Googlebot-News
        "Googlebot-News",
        # Bingbot
        "Mozilla/5.0 (compatible; bingbot/2.0; +http://www.bing.com/bingbot.htm)",
        # Standard Chrome on Android
        "Mozilla/5.0 (Linux; Android 10; K) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Mobile Safari/537.36",
        # Safari on Mac
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 14_4) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    ]
    
    for ua in uas:
        print("-" * 50)
        await test_ua(url, ua)

if __name__ == "__main__":
    asyncio.run(main())

import asyncio
import httpx

async def test_url(url, headers=None, use_http2=False):
    try:
        async with httpx.AsyncClient(timeout=10.0, follow_redirects=True, headers=headers, http2=use_http2) as client:
            resp = await client.get(url)
            print(f"URL: {url}")
            print(f"  HTTP2: {use_http2} | Headers config: {bool(headers)}")
            print(f"  Status: {resp.status_code}")
            print(f"  Length: {len(resp.text)}")
            if resp.status_code == 200:
                print(f"  Snippet: {resp.text[:150].strip()}")
            return resp.status_code == 200
    except Exception as e:
        print(f"  Error: {type(e).__name__} - {e}")
        return False

async def main():
    urls = [
        "https://www.reuters.com/world/canada-regulator-cited-anthropics-claude-mythos-warning-banks-cyber-risks-email-2026-07-13/",
        "https://www.washingtonpost.com/world/2026/07/14/france-bastille-day-ukraine-troops/"
    ]
    
    # 1. Try default crawler headers
    default_headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
            "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.5",
    }
    
    # 2. Try cleaner browser-like headers
    clean_headers = {
        "user-agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
        "accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7",
        "accept-language": "en-US,en;q=0.9",
        "accept-encoding": "gzip, deflate, br",
        "sec-ch-ua": '"Google Chrome";v="123", "Not:A-Brand";v="8", "Chromium";v="123"',
        "sec-ch-ua-mobile": "?0",
        "sec-ch-ua-platform": '"Windows"',
        "sec-fetch-dest": "document",
        "sec-fetch-mode": "navigate",
        "sec-fetch-site": "none",
        "sec-fetch-user": "?1",
        "upgrade-insecure-requests": "1",
    }

    for url in urls:
        print("\n" + "="*80)
        print(f"Testing URL: {url}")
        
        print("\n--- Test 1: Default crawler headers ---")
        await test_url(url, headers=default_headers)
        
        print("\n--- Test 2: Default crawler headers + HTTP/2 ---")
        await test_url(url, headers=default_headers, use_http2=True)
        
        print("\n--- Test 3: Cleaner browser-like headers ---")
        await test_url(url, headers=clean_headers)
        
        print("\n--- Test 4: Cleaner browser-like headers + HTTP/2 ---")
        await test_url(url, headers=clean_headers, use_http2=True)

if __name__ == "__main__":
    asyncio.run(main())

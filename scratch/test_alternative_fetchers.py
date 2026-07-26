import asyncio
import urllib.request
import newspaper
import trafilatura

def test_urllib(url):
    try:
        req = urllib.request.Request(
            url, 
            headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'}
        )
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode('utf-8', errors='ignore')
            print(f"Urllib: Success! Status {response.status}, HTML length: {len(html)}")
            return True
    except Exception as e:
        print(f"Urllib failed: {e}")
        return False

def test_newspaper_download(url):
    try:
        article = newspaper.article(url, language='en')
        print(f"Newspaper: Success! Title: {article.title}, Text length: {len(article.text)}")
        return True
    except Exception as e:
        print(f"Newspaper download failed: {e}")
        return False

def test_trafilatura_download(url):
    try:
        html = trafilatura.fetch_url(url)
        if html:
            text = trafilatura.extract(html)
            print(f"Trafilatura: Success! HTML length: {len(html)}, extracted text length: {len(text) if text else 0}")
            return True
        else:
            print("Trafilatura: Failed (fetch_url returned None)")
            return False
    except Exception as e:
        print(f"Trafilatura download failed: {e}")
        return False

async def main():
    urls = [
        "https://www.reuters.com/world/canada-regulator-cited-anthropics-claude-mythos-warning-banks-cyber-risks-email-2026-07-13/",
        "https://www.washingtonpost.com/world/2026/07/14/france-bastille-day-ukraine-troops/"
    ]
    for url in urls:
        print("\n" + "="*80)
        print(f"Testing URL: {url}")
        
        print("\n--- Test Urllib ---")
        test_urllib(url)
        
        print("\n--- Test Newspaper Download ---")
        test_newspaper_download(url)
        
        print("\n--- Test Trafilatura Download ---")
        test_trafilatura_download(url)

if __name__ == "__main__":
    asyncio.run(main())

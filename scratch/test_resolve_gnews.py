import httpx
import re
from bs4 import BeautifulSoup

def resolve_gnews_url(url: str) -> str:
    print(f"Resolving: {url}")
    try:
        # Request with a normal browser User-Agent
        headers = {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )
        }
        # Do not follow redirects automatically, let's inspect the page
        r = httpx.get(url, headers=headers, follow_redirects=True)
        print(f"Response status: {r.status_code}")
        print(f"Response final URL: {r.url}")
        
        # Look for noscript meta refresh
        soup = BeautifulSoup(r.text, "html.parser")
        meta = soup.find("meta", attrs={"http-equiv": "refresh"})
        if meta and meta.get("content"):
            content = meta["content"]
            # format: "0;url=TARGET_URL"
            parts = content.split("url=")
            if len(parts) > 1:
                target = parts[1]
                print(f"Found target URL in meta refresh: {target}")
                return target
                
        # Look for JavaScript location.replace
        match = re.search(r'window\.location\.replace\("([^"]+)"\)', r.text)
        if match:
            target = match.group(1)
            print(f"Found target URL in JS: {target}")
            return target
            
        with open("/tmp/gnews_response.html", "w", encoding="utf-8") as f:
            f.write(r.text)
        print("Wrote HTML response to /tmp/gnews_response.html")
        print("Could not find target URL in HTML response. Body:")
        print(r.text[:500])
    except Exception as e:
        print(f"Error: {e}")
    return url

if __name__ == "__main__":
    url = "https://news.google.com/rss/articles/CBMi7wFBVV95cUxPYlJRWUhrc0ZzajZscHpwOC1vUFhjQmZPOWNzMUVMZUNObko1cVpPb0I5MFBWOWJiUWU5SllpZFBFd0ZrVkhxS3RpZkpSN0RYZDUyY3ZJQkpOaTU0QVRBa2poR0tLYng2Mm5waVVTTG0ySzlHeTJnOGZHRFhicmlVdXAtSnQ1VFd6dnBWN3J5LXc2cDU3RWR6eFkzMFFDVXQ1N215cWxvUG5QWEVOY01EXzRvZDlKX3J4RFVsZU5oWlg0RUM2NlRoZVhlWkZZT2g0YmN4U3N4Wl96VGk0M1huX3FTaU5sSmRGTWFUSDlfd9IB9AFBVV95cUxPM3QxaUJGTGxRTm1WcVBpclB2UGxfOVhQMUg3MUhtRGtUYW5vX3QwNVNIY0o3VmtIeEhQZ0ZaMlgyekh2eWJvclF4M0Rmb1VSamZaTVBtVDhXYTlVSk5Wd1hqYUNIUXFCbldFa2Z1QzVGdkwzbngydXpERFRxT1RvOWNmYlV4MHNQdjFKZXZWYjZPQkhZUy1iT3hudzJIQmdfLVpQX29Rby1MS0JLNE1IODZuOE5uT3QxUGVIaUNxbzB0QzdBdU1wVjUtaW9nek0wcUZORlBxdHBXRlgxbzR1MVVxd2duLTZpd3BMV2lUMDd2RkZh?oc=5"
    resolve_gnews_url(url)

import httpx

try:
    r = httpx.get("https://api.newsiq.online/health", verify=False)
    print("Status code:", r.status_code)
    print("Response JSON:", r.json())
except Exception as e:
    print("Error:", e)

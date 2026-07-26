import urllib.request
import json

url = "https://api.github.com/repos/Unchartd/NewsIQ/actions/runs/29325749258/jobs"
req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})

try:
    with urllib.request.urlopen(req) as resp:
        data = json.loads(resp.read().decode())
        print("=== Jobs for Run 29325749258 ===")
        for job in data.get("jobs", []):
            print(f"Job: {job['name']} | Status: {job['status']} | Conclusion: {job['conclusion']}")
            print("Steps:")
            for step in job.get("steps", []):
                print(f"  - {step['name']}: {step['status']} ({step['conclusion']})")
except Exception as e:
    print("Error:", e)

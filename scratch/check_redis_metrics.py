import redis
from datetime import datetime, UTC

def check():
    r = redis.Redis(host="redis", port=6379, db=0)
    
    # Check keys
    keys = r.keys("discovery:metrics:*")
    print(f"Metrics keys in DB 0: {keys}")
    
    for k in keys:
        print(f"\n=== Metrics for {k.decode()} ===")
        raw = r.hgetall(k)
        metrics = {k2.decode(): v2.decode() for k2, v2 in raw.items()}
        for name, val in sorted(metrics.items()):
            print(f"  {name}: {val}")

if __name__ == "__main__":
    check()

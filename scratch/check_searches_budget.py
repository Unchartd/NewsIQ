import redis

def check():
    r = redis.Redis(host="redis", port=6379, db=0)
    print("=== Keys in DB 0 ===")
    for k in r.keys("discovery:daily_*"):
        print(f"  {k.decode()}: {r.get(k).decode() if r.get(k) else 'None'}")
        
    r2 = redis.Redis(host="redis", port=6379, db=1)
    print("=== Keys in DB 1 ===")
    for k in r2.keys("discovery:daily_*"):
        print(f"  {k.decode()}: {r2.get(k).decode() if r2.get(k) else 'None'}")

if __name__ == "__main__":
    check()

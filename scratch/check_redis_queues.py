import redis

def check():
    # Connect to Redis DB 1 (Celery broker)
    r = redis.Redis(host="redis", port=6379, db=1)
    
    # List all keys
    keys = r.keys("*")
    print(f"Redis keys in DB 1: {keys}")
    
    # Check queue lengths for lists
    for k in keys:
        try:
            length = r.llen(k)
            print(f"Queue {k.decode()} length: {length}")
        except Exception:
            pass

if __name__ == "__main__":
    check()

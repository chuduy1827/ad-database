"""Lesson 2 - Redis TicketRush lab (day du Step 0-6).
Chay: docker compose up -d  (redis:8 port 6379)
      pip install redis
      python ticketrush.py
"""
import time, uuid, random
from concurrent.futures import ThreadPoolExecutor
import redis

r = redis.Redis(host="localhost", port=6379, decode_responses=True)

def race(fn, n=50):
    with ThreadPoolExecutor(max_workers=n) as pool:
        return list(pool.map(fn, range(n)))

# ---- Step 1 ----
def hold_naive(event, seat, user):
    key = f"hold:{event}:{seat}"
    if r.get(key) is None:
        time.sleep(0.01)
        r.set(key, user, ex=300)
        return True
    return False

def hold_nx(event, seat, user, ttl=300):
    return bool(r.set(f"hold:{event}:{seat}", user, nx=True, ex=ttl))

# ---- Step 2: Lua scripts ----
HOLD = r.register_script("""
if redis.call('SISMEMBER', KEYS[2], ARGV[2]) == 1 then return 0 end
if redis.call('SET', KEYS[1], ARGV[1], 'NX', 'EX', ARGV[3]) then return 1 end
return 0
""")
CONFIRM = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
  redis.call('SADD', KEYS[2], ARGV[2])
  redis.call('DEL', KEYS[1])
  return 1
end
return 0
""")
RELEASE = r.register_script("""
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
""")

def hold(event, seat, user, ttl=300):
    return bool(HOLD(keys=[f"hold:{event}:{seat}", f"sold:{event}"], args=[user, seat, ttl]))

def confirm(event, seat, user):
    return bool(CONFIRM(keys=[f"hold:{event}:{seat}", f"sold:{event}"], args=[user, seat]))

def release(event, seat, user):
    return bool(RELEASE(keys=[f"hold:{event}:{seat}"], args=[user]))

def seat_map(event, seats):
    sold = r.smembers(f"sold:{event}")
    return {s: "sold" if s in sold else "held" if r.exists(f"hold:{event}:{s}") else "free" for s in seats}

# ---- Step 3: flash sale ----
def buy_general(event, user):
    left = r.decr(f"stock:{event}")
    if left < 0:
        r.incr(f"stock:{event}")
        return False
    r.sadd(f"buyers:{event}", user)
    return True

# ---- Step 4: rate limiting ----
def allow_fixed(user, limit=5, window=10):
    key = f"rl:fixed:{user}:{int(time.time() // window)}"
    pipe = r.pipeline()
    pipe.incr(key)
    pipe.expire(key, window, nx=True)
    count, _ = pipe.execute()
    return count <= limit

SLIDING = r.register_script("""
local now, window, limit = tonumber(ARGV[1]), tonumber(ARGV[2]), tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], 0, now - window)
if redis.call('ZCARD', KEYS[1]) < limit then
  redis.call('ZADD', KEYS[1], now, ARGV[4])
  redis.call('PEXPIRE', KEYS[1], window)
  return 1
end
return 0
""")

def allow_sliding(user, limit=5, window_ms=10_000):
    now = int(time.time() * 1000)
    return bool(SLIDING(keys=[f"rl:sliding:{user}"], args=[now, window_ms, limit, uuid.uuid4().hex]))

def try_hold(event, seat, user):
    if not allow_sliding(user):
        return "rate_limited"
    return "ok" if hold(event, seat, user) else "taken"

# ---- Step 5: waiting room ----
def join_queue(event, user):
    r.zadd(f"queue:{event}", {user: time.time()}, nx=True)
    return r.zrank(f"queue:{event}", user) + 1

def admit(event, n):
    return [user for user, _ in r.zpopmin(f"queue:{event}", n)]

# ---- Step 6: stress test ----
def stress():
    r.flushdb()
    SEATS = [f"S{i}" for i in range(1, 21)]
    def buyer(i):
        user = f"user{i}"
        for seat in SEATS:
            if hold("c1", seat, user):
                time.sleep(random.random() * 0.05)
                if confirm("c1", seat, user):
                    return seat
        return None
    got = [s for s in race(buyer, n=100) if s]
    print(len(got), len(set(got)), r.scard("sold:c1"))

if __name__ == "__main__":
    r.flushdb()
    print("Step1 naive winners:", sum(race(lambda i: hold_naive("c1", "A1", f"user{i}"))))
    r.flushdb()
    print("Step1 NX winners:", sum(race(lambda i: hold_nx("c1", "A1", f"user{i}"))))
    r.flushdb()
    print("Step2:", hold("c1","A1","linh"), hold("c1","A1","nam"),
          confirm("c1","A1","nam"), confirm("c1","A1","linh"),
          hold("c1","A1","nam"), seat_map("c1",["A1","A2"]))
    r.flushdb(); r.set("stock:g1", 100)
    ok = race(lambda i: buy_general("g1", f"user{i}"), n=500)
    print("Step3 sold:", sum(ok), r.get("stock:g1"), r.scard("buyers:g1"))
    print("Step4 fixed:", [allow_fixed("linh") for _ in range(8)])
    print("Step5:", [join_queue("c1", n) for n in ["u1","u2","u3"]], admit("c1",2))
    print("Step6:", end=" "); stress()

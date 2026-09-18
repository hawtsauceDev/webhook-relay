import os

import psycopg
import redis

database_url = os.environ["DATABASE_URL"]
redis_url = os.environ["REDIS_URL"]

pg = psycopg.connect(database_url)
print("Postgres OK:", pg._closed == 0)  # closed == 0 means the connection is open

r = redis.Redis.from_url(redis_url)
print("Redis OK:", r.ping())  # ping returns True if redis responds.

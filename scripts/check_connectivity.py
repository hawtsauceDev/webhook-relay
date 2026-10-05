import psycopg
import redis

from src.webhook_relay.config import get_settings

database_url = get_settings().database_url.get_secret_value()
redis_url = get_settings().redis_url

pg = psycopg.connect(database_url)
print("Postgres OK:", pg._closed == 0)  # closed == 0 means the connection is open

r = redis.Redis.from_url(redis_url)
print("Redis OK:", r.ping())  # ping returns True if redis responds.

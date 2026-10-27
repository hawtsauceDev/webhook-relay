import os

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.exc import ArgumentError

test_database_url = os.environ.get("TEST_DATABASE_URL")

if not test_database_url:
    pytest.exit(
        "TEST_DATABASE_URL is not set. Set it to your dedicated test database URL.",
        returncode=2,
    )

try:
    test_url = make_url(test_database_url)
except (ArgumentError, ValueError, TypeError) as exc:
    pytest.exit(f"TEST_DATABASE_URL is invalid: {type(exc).__name__}", returncode=2)

database_name = test_url.database
database_host = test_url.host

if (
    not database_name
    or not database_name.endswith("_test")
    or database_host not in ("localhost", "127.0.0.1")
):
    pytest.exit(
        "Unsafe test database: the database name must end with "
        "'_test' and also use 'localhost' or '127.0.0.1' as the "
        "database host. Check TEST_DATABASE_URL",
        returncode=2,
    )

os.environ["DATABASE_URL"] = test_database_url

from webhook_relay.config import get_settings

get_settings.cache_clear()


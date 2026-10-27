import psycopg.errors

from webhook_relay.db_errors import get_db_error_details


def test_none_returns_empty_details() -> None:
    assert get_db_error_details(None) == (None, None)


def test_non_driver_error_returns_empty_details() -> None:
    assert get_db_error_details(ValueError("boom")) == (None, None)


def test_psycopg_error_reports_sqlstate_but_no_constraint() -> None:
    # Built by hand: no database, so the diagnostics are empty.
    error = psycopg.errors.UniqueViolation("duplicate key")
    sqlstate, constraint = get_db_error_details(error)
    assert sqlstate == "23505"  # PostgreSQL's code for unique_violation
    assert constraint is None


def test_details_never_contain_the_error_message() -> None:
    secret_url = "https://hooks.example.com/token-abc123"
    error = psycopg.errors.UniqueViolation(f"Key (target_url)=({secret_url}) already exists")
    details = get_db_error_details(error)
    assert "token-abc123" not in repr(details)
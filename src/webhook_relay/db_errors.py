import psycopg

PG_UNIQUE_VIOLATION = "23505"


def get_db_error_details(error: BaseException | None) -> tuple[str | None, str | None]:
    """Return (sqlstate, constraint_name) for a psycopg error, else (None, None)."""
    if isinstance(error, psycopg.Error):
        constraint_name = error.diag.constraint_name if error.diag else None
        return error.sqlstate, constraint_name
    return None, None
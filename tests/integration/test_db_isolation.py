from sqlalchemy import select, text
from sqlalchemy.orm import Session

from webhook_relay.database import engine
from webhook_relay.models.subscription import Subscription


def test_insert_and_read_back(db_session: Session) -> None:
    sub=Subscription(
        target_url="https://exmaple.com/hook",
        event_type="order.created",
        active=True
    )
    db_session.add(sub)
    db_session.commit()

    # Fresh query: reads from the db, not from a python object.
    rows = db_session.scalars(select(Subscription)).all()
    assert len(rows) == 1
    assert rows[0].target_url == "https://exmaple.com/hook"

    # A brand new connection can only see COMMITED rows. This proves the 
    # commit really happened, so the next test has something to clean up

    with engine.connect() as conn:
        count = conn.execute(text("SELECT count(*) FROM subscriptions")).scalar_one()
    assert count == 1

def test_table_is_empty_again(db_session: Session) -> None:
    # Deliberately depends on the previous test having commited a row.
    rows = db_session.scalars(select(Subscription)).all()
    assert rows == []

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from webhook_relay.config import get_settings

engine = create_engine(
    get_settings().database_url.get_secret_value(),
    pool_pre_ping=True,
    echo=get_settings().sql_echo,
    connect_args={
        "connect_timeout": 5,
    },
)

SessionLocal = sessionmaker(bind=engine, expire_on_commit=False)

def get_db():
    with SessionLocal() as db:
        yield db
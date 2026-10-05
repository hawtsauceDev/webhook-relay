from typing import Annotated

from fastapi import Depends
from sqlalchemy.orm import session

from webhook_relay.database import get_db

DbSession = Annotated(session, Depends(get_db))
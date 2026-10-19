import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError

from webhook_relay.database import engine
from webhook_relay.routers.events import router as event_router
from webhook_relay.routers.health import router as health_router
from webhook_relay.routers.subscriptions import router as subscription_router

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield

    # Shutdown
    engine.dispose()


app = FastAPI(
    title="Webhook Relay",
    description="A reliable webhook delivery service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.exception_handler(SQLAlchemyError)


async def database_error_handler(
    request: Request, exc: SQLAlchemyError
) -> JSONResponse:
    logger.error(
        "Unhandled database error on %s %s",
        request.method,
        request.url.path,
        exc_info=exc,
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content={"detail": "Internal Server Error"},
    )


app.include_router(health_router)

app.include_router(subscription_router)

app.include_router(event_router)

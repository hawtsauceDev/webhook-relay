from contextlib import asynccontextmanager

from fastapi import FastAPI

from webhook_relay.api.health import router as health_router
from webhook_relay.database import engine

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    yield

    #Shutdown
    engine.dispose()


app = FastAPI(
    title="Webhook Relay",
    description="A reliable webhook delivery service.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(health_router)
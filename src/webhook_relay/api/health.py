from fastapi import APIRouter

from webhook_relay.schemas.health import HealthResponse

router = APIRouter()

@router.get("/health")
def health_check() -> HealthResponse:
    return HealthResponse(status="ok")
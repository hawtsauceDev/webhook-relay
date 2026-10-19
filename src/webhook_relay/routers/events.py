from fastapi import APIRouter, HTTPException, status

from webhook_relay.dependencies import DbSession
from webhook_relay.exceptions import EventIngestionError
from webhook_relay.schemas.event import EventCreate, EventCreateResponse
from webhook_relay.services.events import ingest_event

EVENT_UNPROCESSABLE_MESSAGE = (
    "The request body failed validation. Possible causes: "
    "`event_type` is missing, is not a string, or is not a valid event name "
    "(letters and digits separated by `.`, `_` or `-`, up to 100 characters); "
    "`payload` is missing or is not a JSON object; "
    "`payload` contains NaN, Infinity or NUL (`\\u0000`) characters; "
    "or the body includes unknown extra fields."
)

EVENT_INGEST_FAILED_MESSAGE = "Could not store the event. Please try again later."

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=EventCreateResponse,
    summary="Ingest an incoming event",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": EVENT_UNPROCESSABLE_MESSAGE
        },
        status.HTTP_500_INTERNAL_SERVER_ERROR: {
            "description": "Unexpected database error. No internal details are exposed.",
            "content": {
                "application/json": {"example": {"detail": EVENT_INGEST_FAILED_MESSAGE}}
            },
        },
    },
)
def create_event(db: DbSession, event_data: EventCreate) -> EventCreateResponse:
    """Ingest an event and create one pending delivery per matching subscription.

    The event is stored even if no subscriptions are listening to it.

    `event_type` is normalized (trimmed and lowercased) before matching.
    """
    
    try:
        event, deliveries = ingest_event(db, event_data.event_type, event_data.payload)
    except EventIngestionError:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=EVENT_INGEST_FAILED_MESSAGE,
        ) from None

    delivery_ids: list[int] = []
    for delivery in deliveries:
        delivery_ids.append(delivery.id)
    return EventCreateResponse(
        id=event.id,
        event_type=event.event_type,
        delivery_ids=delivery_ids,
        created_at=event.created_at,
    )

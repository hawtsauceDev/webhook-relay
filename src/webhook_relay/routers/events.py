from fastapi import APIRouter, status

from webhook_relay.dependencies import DbSession
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

router = APIRouter(prefix="/events", tags=["events"])


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    response_model=EventCreateResponse,
    summary="Ingest an incoming event",
    responses={
        status.HTTP_422_UNPROCESSABLE_CONTENT: {
            "description": EVENT_UNPROCESSABLE_MESSAGE
        }
    },
)
def create_event(db: DbSession, event_data: EventCreate) -> EventCreateResponse:
    """This function creates deliveries to listening subscriptions based on incoming events\n
    Event is saved even if no subscriptions are listening to it\n
    event_type is normalized"""
    event, deliveries = ingest_event(db, event_data.event_type, event_data.payload)
    delivery_ids: list[int] = []
    for delivery in deliveries:
        delivery_ids.append(delivery.id)
    return EventCreateResponse(
        id=event.id,
        event_type=event.event_type,
        delivery_ids=delivery_ids,
        created_at=event.created_at,
    )

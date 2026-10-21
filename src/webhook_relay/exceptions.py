class PersistenceError(Exception):
    """An unexpected database failure. Carries no data on purpose."""


class SubscriptionCreationError(PersistenceError):
    def __init__(self) -> None:
        super().__init__("Failed to create subscription")


class SubscriptionAlreadyExists(Exception):
    def __init__(self, existing_id: int | None) -> None:
        super().__init__("Subscription already exists")
        self.existing_id = existing_id


class SubscriptionUpdateError(PersistenceError):
    def __init__(self) -> None:
        super().__init__("Failed to update subscription")


class EventIngestionError(PersistenceError):
    def __init__(self) -> None:
        super().__init__("Failed to ingest event")


class DeliveryAttemptRecordingError(PersistenceError):
    def __init__(self) -> None:
        super().__init__("Failed to record delivery attempt")

from pydantic import BaseModel


class PubSubMessage(BaseModel):
    """Represents the PubSub message structure from the GCS event trigger."""

    message: dict
    subscription: str


class GCSMessageData(BaseModel):
    """Represents the GCS Object Finalize event data."""

    bucket: str
    name: str
    timeCreated: str

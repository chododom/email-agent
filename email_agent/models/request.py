from pydantic import BaseModel, Field
from datetime import datetime
import base64
import json
from typing import Any, Dict

from pydantic.v1.fields import ModelField


class DecodedPushData(Dict[str, Any]):
    """
    A custom Pydantic type that takes a Base64 encoded string
    (from the PubSub 'data' field) and returns the decoded Gmail JSON payload
    as a dictionary.
    """

    @classmethod
    def __get_validators__(cls):
        yield cls.validate

    @classmethod
    def validate(cls, v: str, field: ModelField) -> Dict[str, Any]:
        if not isinstance(v, str):
            raise TypeError("Input must be a string (Base64 encoded data).")

        try:
            decoded_bytes = base64.b64decode(v)
            decoded_json_string = decoded_bytes.decode("utf-8")
            decoded_payload = json.loads(decoded_json_string)

            if "historyId" not in decoded_payload:
                raise ValueError(
                    "Decoded payload is missing the required 'historyId' field."
                )

            return decoded_payload

        except base64.binascii.Error:
            raise ValueError("Input data is not valid Base64.")
        except json.JSONDecodeError:
            raise ValueError("Decoded Base64 content is not valid JSON.")
        except Exception as e:
            raise ValueError(f"Failed to process payload: {e}")


class EmailPushMessage(BaseModel):
    """Represents the data content of a Gmail API push trigger."""

    data: DecodedPushData
    message_id: str = Field(..., alias="messageId")
    publish_time: datetime = Field(..., alias="publishTime")


class EmailPush(BaseModel):
    """Represents the PubSub message structure from the Gmail API trigger."""

    message: EmailPushMessage
    subscription: str

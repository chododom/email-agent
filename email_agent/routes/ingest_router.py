from fastapi import APIRouter, HTTPException
from email_agent.utils.logger import logger
import base64
import json
from typing import Optional
from email_agent.models.ingest import PubSubMessage, GCSMessageData
from email_agent.services.ingestion import (
    load_and_chunk_gcs_file,
    get_multilingual_embeddings,
    upsert_to_vector_search,
)


router = APIRouter()


def decode_message(message: dict) -> Optional[GCSMessageData]:
    """
    Decodes the PubSub base64 payload to get GCS metadata.
    """
    try:
        encoded_data = message["data"]
        decoded_data = base64.b64decode(encoded_data).decode("utf-8")
        gcs_data = json.loads(decoded_data)

        logger.info(f"GCS data for ingestion: {gcs_data}")
        return GCSMessageData(**gcs_data)

    except Exception as e:
        logger.error(f"Error decoding PubSub message: {e}")
        return None


@router.post("/ingest")
async def ingest_gcs_file(pubsub_data: PubSubMessage):
    """
    Handles the ingestion of documents uploaded to the watched GCS bucket into the deployed Vector Search index.
    """
    gcs_event_data = decode_message(pubsub_data.message)

    if not gcs_event_data:
        raise HTTPException(status_code=400, detail="Invalid PubSub message data.")

    bucket = gcs_event_data.bucket
    name = gcs_event_data.name
    gcs_file_path = f"gs://{bucket}/{name}"

    logger.info(f"Processing new file for ingestion: {gcs_file_path}")

    try:
        # Split document into chunks and embed them
        chunks = load_and_chunk_gcs_file(bucket, name)
        embeddings = get_multilingual_embeddings(chunks)

    except Exception as e:
        logger.error(f"Ingestion pipeline failed for {gcs_file_path}: {e}")
        # Return 200 OK to stop PubSub retrying on bad document data
        return {"status": "error", "message": f"Processing failed: {e}"}

    # Upsert new chunks and embeddings to the Vector Search index
    try:
        await upsert_to_vector_search(embeddings, chunks)
    except Exception as e:
        logger.error(f"Vector Search upsert failed for {gcs_file_path}: {e}")
        raise HTTPException(status_code=500, detail="Vertex AI Upsert failed.")

    return HTTPException(status_code=200)

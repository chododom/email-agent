from google.cloud import firestore
from typing import Optional
from fastapi import HTTPException
from email_agent.utils.logger import logger
from email_agent.config import CFG


try:
    db = firestore.AsyncClient(project=CFG.project_id, database=CFG.firestore_name)
except Exception as e:
    msg = f"Failed to initialize Firestore client: {e}"
    logger.error(msg)
    raise HTTPException(status_code=500, detail=msg)


class FirestoreService:
    """
    Manages all persistent state interaction with Google Firestore.
    """

    def __init__(self):
        self.db = db

    async def get_last_history_id(self) -> Optional[str]:
        """
        Retrieves the last successfully processed Gmail history ID.
        """
        try:
            doc_ref = self.db.collection(CFG.firestore_config_collection).document(
                CFG.gmail_state_doc_id
            )
            doc = await doc_ref.get()

            if doc.exists:
                data = doc.to_dict()
                return data.get("last_processed_history_id")
            else:
                return None

        except Exception as e:
            logger.error(f"Error fetching history ID: {e}")
            return None

    async def set_last_history_id(self, history_id: str) -> None:
        """
        Saves the newest Gmail history ID for the next check.
        """
        try:
            doc_ref = self.db.collection(CFG.firestore_config_collection).document(
                CFG.gmail_state_doc_id
            )
            await doc_ref.set(
                {
                    "last_processed_history_id": history_id,
                    "timestamp": firestore.SERVER_TIMESTAMP,
                }
            )

        except Exception as e:
            msg = f"Error saving history ID {history_id}: {e}"
            logger.error(msg)
            raise HTTPException(status_code=500, detail=msg)

    async def check_and_set_processed_message(self, message_id: str) -> bool:
        """
        Checks if a message ID has been processed. If not, sets it as processed
        and returns True. If it has been processed, returns False.
        """
        doc_ref = self.db.collection("processed_messages").document(message_id)

        @firestore.async_transactional
        async def update_in_transaction(
            transaction: firestore.AsyncTransaction, operation_data
        ):
            doc = await operation_data.get(transaction=transaction)
            if doc.exists:
                return False

            transaction.set(doc_ref, {"timestamp": firestore.SERVER_TIMESTAMP})
            return True

        try:
            transaction = self.db.transaction()
            return await update_in_transaction(transaction, doc_ref)
        except Exception as e:
            logger.error(f"Transaction failed for message {message_id}: {e}")
            raise HTTPException(
                status_code=500, detail=f"Failed to process message check: {e}"
            )


firestore_service = FirestoreService()

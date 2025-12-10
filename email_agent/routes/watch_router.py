from fastapi import APIRouter, HTTPException
from email_agent.config import CFG
from email_agent.services.gmail import get_gmail_service
from email_agent.utils.logger import logger
from email_agent.services.firestore import firestore_service


router = APIRouter()


@router.post("/renew-watch")
async def renew_watch_instruction():
    """
    Handles the renewal of a watch request on the configured Gmail inbox.
    """
    gmail_service = get_gmail_service()

    # Define the watch request body
    watch_request = {
        "labelIds": ["UNREAD"],  # Watch the UNREAD messages in the Inbox
        "topicName": CFG.pubsub_topic,
    }

    try:
        # Execute the watch command to renew the subscription
        response = (
            gmail_service.users()
            .watch(userId=CFG.user_email, body=watch_request)
            .execute()
        )

        new_history_id = response.get("historyId")
        if new_history_id:
            await firestore_service.set_last_history_id(new_history_id)
            logger.info(f"Renewed historyId saved: {new_history_id}")
        else:
            logger.warning("Watch command did not return a historyId.")

        logger.info(f"Watch renewed. New expiration: {response.get('expiration')}")

        return {"status": "success", "message": "Gmail watch successfully renewed."}

    except Exception as e:
        msg = f"Error renewing watch: {e}"
        logger.error(msg)
        raise HTTPException(status_code=500, detail=msg)

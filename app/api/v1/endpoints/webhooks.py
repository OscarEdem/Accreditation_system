import json
import logging
import httpx
from fastapi import APIRouter, Request, status, Response

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/sendgrid")
async def sendgrid_webhook(request: Request):
    """
    Webhook to receive Bounce, Dropped, and Spam Complaint notifications from SendGrid.
    """
    try:
        body = await request.body()
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Failed to decode SendGrid webhook payload")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    # SendGrid sends an array of events
    if isinstance(payload, list):
        for event in payload:
            event_type = event.get("event")
            email = event.get("email")
            
            if event_type in ["bounce", "dropped"]:
                logger.warning(f"SENDGRID BOUNCE/DROP DETECTED for email: {email}")
                # TODO: Update database to flag this user/application email as invalid
                
            elif event_type == "spamreport":
                logger.warning(f"SENDGRID SPAM COMPLAINT DETECTED for email: {email}")
                
    return Response(status_code=status.HTTP_200_OK)
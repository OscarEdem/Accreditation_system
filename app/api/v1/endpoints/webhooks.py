import json
import logging
import httpx
from fastapi import APIRouter, Request, status, Response
from sendgrid.helpers.eventwebhook import EventWebhook
from app.config.settings import settings

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/sendgrid")
async def sendgrid_webhook(request: Request):
    """
    Webhook to receive Bounce, Dropped, and Spam Complaint notifications from SendGrid.
    """
    # SECURITY: Verify the request actually came from SendGrid
    public_key_str = getattr(settings, "SENDGRID_WEBHOOK_PUBLIC_KEY", None)
    if public_key_str:
        ew = EventWebhook()
        public_key = ew.convert_public_key_to_ecdsa(public_key_str)
        signature = request.headers.get('X-Twilio-Email-Event-Webhook-Signature')
        timestamp = request.headers.get('X-Twilio-Email-Event-Webhook-Timestamp')
        body = await request.body()
        
        if not signature or not timestamp or not ew.verify_signature(body.decode('utf-8'), signature, timestamp, public_key):
            logger.warning("FORGERY ATTEMPT: Invalid SendGrid Webhook Signature!")
            return Response(status_code=status.HTTP_403_FORBIDDEN)
    else:
        logger.warning("SENDGRID_WEBHOOK_PUBLIC_KEY not set. Webhook is running unsecured!")

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
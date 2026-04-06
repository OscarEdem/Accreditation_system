import json
import logging
import httpx
from fastapi import APIRouter, Request, status, Response

router = APIRouter()
logger = logging.getLogger(__name__)

@router.post("/ses")
async def ses_notification_webhook(request: Request):
    """
    Webhook to receive Bounce and Complaint notifications from Amazon SNS (triggered by SES).
    """
    try:
        # SNS sends data as text/plain, so we must parse the raw body
        body = await request.body()
        payload = json.loads(body)
    except json.JSONDecodeError:
        logger.error("Failed to decode SNS webhook payload")
        return Response(status_code=status.HTTP_400_BAD_REQUEST)

    message_type = payload.get("Type")
    
    # 1. Handle SNS Subscription Confirmation
    if message_type == "SubscriptionConfirmation":
        subscribe_url = payload.get("SubscribeURL")
        if subscribe_url:
            logger.info(f"Confirming SES/SNS Subscription: {subscribe_url}")
            async with httpx.AsyncClient() as client:
                await client.get(subscribe_url)
        return Response(status_code=status.HTTP_200_OK)

    # 2. Handle Actual Notifications (Bounces & Complaints)
    if message_type == "Notification":
        message_str = payload.get("Message", "{}")
        try:
            message_data = json.loads(message_str)
            notification_type = message_data.get("notificationType")
            
            if notification_type == "Bounce":
                bounced_recipients = message_data.get("bounce", {}).get("bouncedRecipients", [])
                for recipient in bounced_recipients:
                    email = recipient.get("emailAddress")
                    logger.warning(f"SES BOUNCE DETECTED for email: {email}")
                    # TODO: Update database to flag this user/application email as invalid
                    
            elif notification_type == "Complaint":
                logger.warning("SES SPAM COMPLAINT DETECTED")
        except json.JSONDecodeError:
            logger.error("Failed to decode inner SNS Message")
            
    return Response(status_code=status.HTTP_200_OK)
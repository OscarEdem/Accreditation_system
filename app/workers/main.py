import os
import boto3
import requests
import logging
import asyncio
import time
from celery import Celery
from celery.signals import worker_process_init
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from redis.asyncio import Redis
from botocore.exceptions import ClientError
from app.config.settings import settings

logger = logging.getLogger(__name__)

celery_app = Celery(
    "accreditation_worker",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="UTC",
    enable_utc=True,
)

# Only apply SSL configurations if the URL actually uses the rediss:// scheme (e.g. AWS ElastiCache)
if settings.CELERY_BROKER_URL.startswith("rediss://"):
    celery_app.conf.update(broker_use_ssl={"ssl_cert_reqs": "none"})
if settings.CELERY_RESULT_BACKEND.startswith("rediss://"):
    celery_app.conf.update(redis_backend_use_ssl={"ssl_cert_reqs": "none"})

@worker_process_init.connect
def init_worker(**kwargs):
    logger.info("Starting up Accreditation Celery Worker...")
    
    async def run_async_checks():
        # 1. DB Check
        safe_db_url = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "Local/Unknown"
        logger.info(f"Initializing Database connection to: {safe_db_url}")
        try:
            engine = create_async_engine(settings.DATABASE_URL)
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection successful.")
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
        
        # 2. Redis Check
        safe_redis_url = settings.CELERY_BROKER_URL.split("@")[-1] if "@" in settings.CELERY_BROKER_URL else settings.CELERY_BROKER_URL
        logger.info(f"Initializing Redis connection to: {safe_redis_url}")
        try:
            redis_client = Redis.from_url(
                settings.CELERY_BROKER_URL,
                socket_connect_timeout=5,
                socket_timeout=5,
                ssl_cert_reqs="none"
            )
            await asyncio.wait_for(redis_client.ping(), timeout=5.0)
            logger.info("Redis connection successful.")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

    # Execute the async checks inside the sync Celery initialization
    asyncio.run(run_async_checks())
    
    # 3. S3 Check
    logger.info(f"AWS S3 configured for bucket: {settings.S3_BUCKET_NAME} in region {settings.AWS_REGION}")
    try:
        s3_client = boto3.client(
            "s3",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        s3_client.head_bucket(Bucket=settings.S3_BUCKET_NAME)
        logger.info("AWS S3 connection successful.")
    except Exception as e:
        logger.error(f"AWS S3 connection failed: {e}")
        
    logger.info("Celery worker startup checks complete.")


@celery_app.task(name="send_email_notification", bind=True, max_retries=3)
def send_email_notification(self, recipient_email: str, subject: str, body: str):
    """Background task to send email notifications to users using AWS SES."""
    logger.info(f"Preparing to send email to {recipient_email} - Subject: {subject}")
    
    if not settings.AWS_SES_SENDER:
        logger.warning("AWS_SES_SENDER is not configured. Simulating email send.")
        time.sleep(2)
        return {"status": "simulated", "recipient": recipient_email}
        
    try:
        ses_client = boto3.client(
            "ses",
            aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
            region_name=settings.AWS_REGION
        )
        
        response = ses_client.send_email(
            Source=settings.AWS_SES_SENDER,
            Destination={
                'ToAddresses': [recipient_email]
            },
            Message={
                'Subject': {
                    'Data': subject,
                    'Charset': 'UTF-8'
                },
                'Body': {
                    'Text': {
                        'Data': body,
                        'Charset': 'UTF-8'
                    }
                }
            }
        )
        
        logger.info(f"Successfully sent email to {recipient_email}. Message ID: {response.get('MessageId')}")
        return {"status": "success", "recipient": recipient_email, "message_id": response.get("MessageId")}
    except ClientError as e:
        logger.error(f"AWS SES Error sending email to {recipient_email}: {e.response['Error']['Message']}")
        raise self.retry(exc=e, countdown=60)
    except Exception as exc:
        logger.error(f"Failed to send email to {recipient_email}: {exc}")
        # Retry the task in 60 seconds in case of transient network issues
        raise self.retry(exc=exc, countdown=60)
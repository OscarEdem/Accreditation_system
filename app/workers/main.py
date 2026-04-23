import os
import boto3
import requests
import logging
import asyncio
import time
from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_process_init
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from redis.asyncio import Redis
from botocore.exceptions import ClientError
from sendgrid import SendGridAPIClient
from sendgrid.helpers.mail import Mail, Content, Cc
from app.config.settings import settings
from app.core.email import generate_html_email
from app.services.translations import TranslationService

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
    beat_schedule={
        "daily-gdpr-scrub": {
            "task": "scrub_gdpr_data",
            "schedule": crontab(hour=0, minute=0),  # Runs daily at Midnight UTC
        }
    }
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
            redis_kwargs = {
                "socket_connect_timeout": 5,
                "socket_timeout": 5
            }
            if settings.CELERY_BROKER_URL.startswith("rediss://"):
                redis_kwargs["ssl_cert_reqs"] = "none"
                
            redis_client = Redis.from_url(settings.CELERY_BROKER_URL, **redis_kwargs)
            await asyncio.wait_for(redis_client.ping(), timeout=5.0)
            logger.info("Redis connection successful.")
        except Exception as e:
            logger.error(f"Redis connection failed: {e}")

    # Execute the async checks inside the sync Celery initialization
    asyncio.run(run_async_checks())
    
    # 3. S3 Check
    logger.info(f"AWS S3 configured for bucket: {settings.S3_BUCKET_NAME} in region {settings.AWS_REGION}")
    if settings.S3_BUCKET_NAME == "local-dummy-bucket":
        logger.info("Local dummy S3 bucket detected. Skipping AWS connection check.")
    else:
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

async def _is_country_team_org_admin(email: str) -> bool:
    """Helper to dynamically check if an email belongs to an org_admin of a Country Team."""
    try:
        engine = create_async_engine(settings.DATABASE_URL)
        try:
            async with engine.connect() as conn:
                # Using raw SQL to avoid model circular imports inside the worker
                query = text("""
                    SELECT u.role, o.type 
                    FROM users u 
                    LEFT JOIN organizations o ON u.organization_id = o.id 
                    WHERE u.email = :email LIMIT 1
                """)
                result = await conn.execute(query, {"email": email})
                row = result.fetchone()
                if row:
                    role, org_type = row
                    return role == "org_admin" and org_type == "Country Team"
                return False
        finally:
            await engine.dispose()  # Prevent database connection leaks
    except Exception as e:
        logger.error(f"Failed to check user role for {email}: {e}")
        return False

@celery_app.task(name="send_email_notification", bind=True, max_retries=3)
def send_email_notification(self, recipient_email: str, subject: str = None, body: str = None, template_key: str = None, language: str = "en", context: dict = None, cc_emails: list = None):
    """Background task to send email notifications to users using SendGrid."""
    if not recipient_email:
        logger.error("Cannot send email: recipient_email is empty.")
        return {"status": "failed", "reason": "empty recipient"}

    if template_key:
        translations = TranslationService()
        ctx = context or {}
        subject = translations.get_string(f"{template_key}_subject", language, **ctx)
        body = translations.get_string(f"{template_key}_body", language, **ctx)

    # 1. Initialize CC list
    final_cc_emails = list(cc_emails) if cc_emails else []
    
    # 2. Enforce global CC rule for Country Team org_admins only
    if asyncio.run(_is_country_team_org_admin(recipient_email)):
        # Fetch from environment variable
        cc_env = os.getenv("ORG_ADMIN_CC_EMAILS")
        if cc_env:
            required_ccs = [email.strip() for email in cc_env.split(",") if email.strip()]
            
            for required_cc in required_ccs:
                if required_cc != recipient_email and required_cc not in final_cc_emails:
                    final_cc_emails.append(required_cc)

    logger.info(f"Preparing to send email to {recipient_email} - Subject: {subject}")
    
    sendgrid_api_key = os.getenv("SENDGRID_API_KEY")
    from_email = os.getenv("SENDGRID_FROM_EMAIL", "accreditation@fasigms.africa")
    
    if not sendgrid_api_key:
        logger.warning("SENDGRID_API_KEY is not configured. Simulating email send.")
        time.sleep(2)
        return {"status": "simulated", "recipient": recipient_email}
        
    html_body = generate_html_email(subject, body, lang=language)
    
    message = Mail(
        from_email=from_email,
        to_emails=recipient_email,
        subject=subject
    )
    
    # Explicitly define MIME types for maximum email client compatibility
    message.add_content(Content("text/plain", body))
    message.add_content(Content("text/html", html_body))
        
    # 3. Attach CCs to the SendGrid Mail object
    if final_cc_emails:
        for cc_email in final_cc_emails:
            message.add_cc(Cc(cc_email))

    try:
        sg = SendGridAPIClient(sendgrid_api_key)
        response = sg.send(message)
        
        logger.info(f"Successfully sent SendGrid email to {recipient_email}. Status Code: {response.status_code}")
        return {"status": "success", "recipient": recipient_email, "status_code": response.status_code}
    except Exception as exc:
        error_details = str(exc)
        # Extract exact SendGrid JSON error (e.g., "invalid email address")
        if hasattr(exc, 'body'):
            error_details = f"{exc} - Details: {exc.body}"
            
        logger.error(f"Failed to send email to {recipient_email} via SendGrid: {error_details}")
        
        # Do not retry on 4xx Client Errors (e.g., Invalid Email Format) because they will never succeed
        if hasattr(exc, 'status_code') and str(exc.status_code).startswith('4'):
            logger.warning(f"Dropping email task to {recipient_email}: Client error {exc.status_code} cannot be retried.")
            return {"status": "failed", "reason": error_details}
            
        # Retry the task in 60 seconds in case of transient network/server issues (5xx)
        raise self.retry(exc=exc, countdown=60)

@celery_app.task(name="scrub_gdpr_data", bind=True)
def scrub_gdpr_data(self, days_after_end: int = 30):
    """Scheduled task to permanently delete PII and S3 documents after a tournament ends."""
    logger.info(f"Starting GDPR data scrubbing task for tournaments ended {days_after_end} days ago...")
    
    async def run_scrub(days):
        from datetime import timedelta
        from sqlalchemy.orm import sessionmaker, selectinload
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import AsyncSession
        from app.models.application import Application
        from app.models.participant import Participant
        from app.models.tournament import Tournament
        
        engine = create_async_engine(settings.DATABASE_URL)
        AsyncSessionLocal = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
        
        s3_client = boto3.client(
            "s3", aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY, region_name=settings.AWS_REGION
        )
        s3_prefix = f"https://{settings.S3_BUCKET_NAME}.s3.{settings.AWS_REGION}.amazonaws.com/"

        async with AsyncSessionLocal() as session:
            # Find applications for tournaments that ended more than 30 days ago
            cutoff_date = datetime.now(timezone.utc).date() - timedelta(days=days)
            
            stmt = (
                select(Application)
                .join(Participant, Participant.application_id == Application.id)
                .join(Tournament, Participant.tournament_id == Tournament.id)
                .options(selectinload(Application.documents))
                .where(Tournament.end_date <= cutoff_date)
                .where(Application.is_gdpr_scrubbed == False)
            )
            
            applications = (await session.execute(stmt)).scalars().all()
            scrub_count = 0
            
            for app in applications:
                keys_to_delete = []
                
                if app.photo_url and app.photo_url.startswith(s3_prefix):
                    keys_to_delete.append({"Key": app.photo_url.replace(s3_prefix, "")})
                
                for doc in app.documents:
                    if doc.file_url and doc.file_url.startswith(s3_prefix):
                        keys_to_delete.append({"Key": doc.file_url.replace(s3_prefix, "")})
                        doc.file_url = "REDACTED"
                
                # 1. Permanently delete images/documents from AWS S3
                if keys_to_delete and settings.S3_BUCKET_NAME:
                    try:
                        s3_client.delete_objects(Bucket=settings.S3_BUCKET_NAME, Delete={"Objects": keys_to_delete})
                    except Exception as e:
                        logger.error(f"S3 deletion failed for App {app.id}: {e}")
                
                # 2. Scrub PII from PostgreSQL
                app.first_name = "REDACTED"
                app.last_name = "REDACTED"
                app.email = f"redacted_{app.id}@example.com"
                app.photo_url = None
                app.dob = None
                app.gender = None
                app.is_gdpr_scrubbed = True
                scrub_count += 1
                
            if scrub_count > 0:
                await session.commit()
                logger.info(f"Successfully scrubbed {scrub_count} applications for GDPR compliance.")
            else:
                logger.info("No applications found needing GDPR scrubbing today.")
                
    asyncio.run(run_scrub(days_after_end))
import logging
import boto3
import uvicorn
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from redis.asyncio import Redis
from app.api.v1.router import api_router
from app.config.settings import settings
from app.workers.main import send_email_notification

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def run_startup_checks():
    """Runs external connection checks in the background to avoid blocking API boot sequence."""
    
    # 1. Database Check
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
    safe_redis_url = settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL
    logger.info(f"Initializing Redis connection to: {safe_redis_url}")
    try:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=5,
            socket_timeout=5,
            ssl_cert_reqs="none"
        )
        await asyncio.wait_for(redis_client.ping(), timeout=10.0)
        logger.info("Redis connection successful.")
    except asyncio.TimeoutError:
        logger.error("Redis connection timed out during startup.")
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
    
    # 3. AWS S3 Check
    logger.info(f"AWS S3 configured for bucket: {settings.S3_BUCKET_NAME} in region {settings.AWS_REGION}")
    
    def check_s3_sync():
        """Synchronous wrapper for boto3 to run in a separate thread."""
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
            
    # Offload the blocking boto3 network call to a thread so it doesn't freeze FastAPI
    await asyncio.to_thread(check_s3_sync)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Accreditation Management System API...")
    
    # Fire-and-forget: dispatch the checks to the background!
    # Uvicorn will NOT wait for this to finish before answering health checks.
    asyncio.create_task(run_startup_checks())
        
    logger.info("Application startup checks dispatched. Verifying bind to port 8000 via Uvicorn...")
    
    yield
    
    logger.info("Shutting down Accreditation Management System API...")

app = FastAPI(
    title="Accreditation Management System API",
    description="Production-grade API for managing tournament accreditations, participants, and secure zone access.",
    version="1.0.0",
    lifespan=lifespan
)

# --- CORS Configuration ---
# This allows your Next.js/React frontend to communicate with the API without browser security blocks.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In strict production, replace "*" with your frontend's exact domain (e.g., ["https://accra2026.com"])
    allow_credentials=True,
    allow_methods=["*"],  # Allows GET, POST, PUT, DELETE, etc.
    allow_headers=["*"],  # Allows Authorization (JWT) and Content-Type headers
)

# --- Router Registration ---
app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Health Check"])
def read_root():
    """Root endpoint for ALB health checks"""
    return {"status": "healthy", "service": "ams-fastapi", "version": "1.0"}

@app.get("/health", tags=["Health Check"])
def health_check():
    """Dedicated health endpoint"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

@app.post("/test-email", tags=["Testing"])
def trigger_test_email(email: str):
    """Test endpoint to trigger a Celery background task."""
    task = send_email_notification.delay(email, "Test Subject", "Hello from AWS Celery!")
    return {"message": "Email task dispatched!", "task_id": task.id}

if __name__ == "__main__":
    # Allows running the app locally via `python app/main.py`
    uvicorn.run(app, host="0.0.0.0", port=8000)
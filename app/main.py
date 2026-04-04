import logging
import boto3
import uvicorn
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from fastapi import FastAPI
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from redis.asyncio import Redis
from app.api.v1.router import api_router
from app.config.settings import settings

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up Accreditation Management System API...")
    
    # Log Database configuration (masking password for security)
    safe_db_url = settings.DATABASE_URL.split("@")[-1] if "@" in settings.DATABASE_URL else "Local/Unknown"
    logger.info(f"Initializing Database connection to: {safe_db_url}")
    try:
        engine = create_async_engine(settings.DATABASE_URL)
        async with engine.begin() as conn:
            await conn.execute(text("SELECT 1"))
        logger.info("Database connection successful.")
    except Exception as e:
        logger.error(f"Database connection failed: {e}")
    
    # Log Redis configuration (masking password if present)
    safe_redis_url = settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL
    logger.info(f"Initializing Redis connection to: {safe_redis_url}")
    try:
        redis_client = Redis.from_url(
            settings.REDIS_URL,
            socket_connect_timeout=5,
            socket_timeout=5,
            ssl_cert_reqs="none"
        )
        await asyncio.wait_for(redis_client.ping(), timeout=5.0)
        logger.info("Redis connection successful.")
    except asyncio.TimeoutError as e:
        logger.error("Redis connection timed out during startup.")
        raise e
    except Exception as e:
        logger.error(f"Redis connection failed: {e}")
        raise e
    
    # Log S3 configuration
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
        
    logger.info("Application startup checks complete. Verifying bind to port 8000 via Uvicorn...")
    
    yield
    
    logger.info("Shutting down Accreditation Management System API...")

app = FastAPI(
    title="Participant Data Collection API",
    description="MVP for participant data collection",
    version="1.0.0",
    lifespan=lifespan
)

app.include_router(api_router, prefix="/api/v1")

@app.get("/", tags=["Health Check"])
def read_root():
    """Root endpoint for ALB health checks"""
    return {"status": "healthy", "service": "ams-fastapi", "version": "1.0"}

@app.get("/health", tags=["Health Check"])
def health_check():
    """Dedicated health endpoint"""
    return {"status": "ok", "timestamp": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")}

if __name__ == "__main__":
    # Allows running the app locally via `python app/main.py`
    uvicorn.run(app, host="0.0.0.0", port=8000)
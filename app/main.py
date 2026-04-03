import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
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
    
    # Log Redis configuration (masking password if present)
    safe_redis_url = settings.REDIS_URL.split("@")[-1] if "@" in settings.REDIS_URL else settings.REDIS_URL
    logger.info(f"Initializing Redis connection to: {safe_redis_url}")
    
    # Log S3 configuration
    logger.info(f"AWS S3 configured for bucket: {settings.S3_BUCKET_NAME} in region {settings.AWS_REGION}")
    
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
async def health_check():
    """
    Root endpoint used by AWS ALB / ECS for health checks.
    """
    return {"status": "ok", "message": "Accreditation Management System API is running."}
import logging
import boto3
import uvicorn
from contextlib import asynccontextmanager
import asyncio
from datetime import datetime, timezone
from typing import Literal
from fastapi import FastAPI, Depends, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy import text
from redis.asyncio import Redis
import jwt
from app.core.tenant import tenant_user_id, tenant_role, tenant_org_id
from app.api.v1.router import api_router
from app.config.settings import settings
from app.workers.main import send_email_notification
from app.api.deps import RoleChecker
from app.models.user import User

allow_admin = RoleChecker(["admin", "loc_admin"])

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
        redis_kwargs = {
            "socket_connect_timeout": 5,
            "socket_timeout": 5
        }
        if settings.REDIS_URL.startswith("rediss://"):
            redis_kwargs["ssl_cert_reqs"] = "none"
            
        redis_client = Redis.from_url(settings.REDIS_URL, **redis_kwargs)
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
        if settings.S3_BUCKET_NAME == "local-dummy-bucket":
            logger.info("Local dummy S3 bucket detected. Skipping AWS connection check.")
            return
            
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
    
    # Initialize Redis globally for the middleware
    redis_kwargs = {
        "socket_connect_timeout": 5,
        "socket_timeout": 5
    }
    if settings.REDIS_URL.startswith("rediss://"):
        redis_kwargs["ssl_cert_reqs"] = "none"
    app.state.redis = Redis.from_url(settings.REDIS_URL, **redis_kwargs)

    # Fire-and-forget: dispatch the checks to the background!
    # Uvicorn will NOT wait for this to finish before answering health checks.
    asyncio.create_task(run_startup_checks())
        
    logger.info("Application startup checks dispatched. Verifying bind to port 8000 via Uvicorn...")
    
    yield
    
    await app.state.redis.aclose()
    logger.info("Shutting down Accreditation Management System API...")

app = FastAPI(
    title="Accreditation Management System API",
    description="Production-grade API for managing tournament accreditations, participants, and secure zone access.",
    version="1.0.0",
    lifespan=lifespan,
    swagger_ui_parameters={"persistAuthorization": True}
)

EXACT_PUBLIC_PATHS = ["/", "/health", "/openapi.json", "/docs"]

PREFIX_PUBLIC_PATHS = [
    "/api/v1/auth/login", "/api/v1/auth/register",
    "/api/v1/auth/forgot-password", "/api/v1/auth/reset-password",
    "/api/v1/auth/accept-invite", "/api/v1/auth/resend-invite",
    "/api/v1/public/stats", "/api/v1/applications/public", 
    "/api/v1/applications/track/status",
    "/api/v1/applications/options/roles",
    "/api/v1/webhooks/sendgrid"
]

@app.middleware("http")
async def global_security_middleware(request: Request, call_next):
    """
    Global middleware that enforces the Redis session invariant on EVERY request.
    This guarantees that a developer forgetting `Depends(get_current_user)` 
    will not accidentally expose an endpoint.
    """
    path = request.url.path
    
    # 1. Bypass auth for strictly public paths
    is_public_get = request.method == "GET" and (
        path.startswith("/api/v1/tournaments") or 
        path.startswith("/api/v1/organizations")
    )
    
    if path in EXACT_PUBLIC_PATHS or any(path.startswith(p) for p in PREFIX_PUBLIC_PATHS) or path.startswith("/api/v1/scan/live-alerts") or is_public_get:
        return await call_next(request)
        
    # 2. Extract and Verify Token
    auth_header = request.headers.get("Authorization")
    
    if not auth_header or not auth_header.startswith("Bearer "):
        return JSONResponse(status_code=401, content={"detail": "Missing or invalid authentication token"})
        
    token = auth_header.split(" ")[1]
    try:
        payload = jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
        user_id = payload.get("user_id")
        session_id = payload.get("session_id")
        
        # 3. Global Redis Session Enforcement (Centralized Revocation)
        redis_client: Redis = request.app.state.redis
        active_session = await redis_client.get(f"active_session:{user_id}")

        if active_session:
            active_session_str = active_session.decode("utf-8")
            if active_session_str == "revoked" or active_session_str != session_id:
                return JSONResponse(status_code=401, content={"detail": "Session expired, revoked, or invalid."})
        else:
            # RELAXED RULE: If Redis was cleared, trust the valid JWT and restore the session.
            await redis_client.set(f"active_session:{user_id}", session_id, ex=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60)
        # 4. Set Global Tenant Context for SQLAlchemy Scoping
        tenant_user_id.set(user_id)
        tenant_role.set(payload.get("role"))
        tenant_org_id.set(payload.get("org_id"))
        
    except jwt.ExpiredSignatureError:
        return JSONResponse(status_code=401, content={"detail": "Token has expired"})
    except jwt.InvalidTokenError:
        return JSONResponse(status_code=401, content={"detail": "Invalid token"})
        
    return await call_next(request)

# --- CORS Configuration ---
# ADDED LAST so it acts as the outermost middleware layer. 
# It will now successfully append CORS headers to all 401 responses!
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
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
def trigger_test_email(
    email: str,
    language: Literal['en', 'fr', 'pt', 'es', 'ar'] = "en",
    current_user: User = Depends(allow_admin)
):
    """Test endpoint to trigger a Celery background task."""
    task = send_email_notification.delay(
        recipient_email=email,
        template_key="test_email",
        language=language,
        context={
            "first_name": current_user.first_name,
            "test_link": f"{settings.FRONTEND_URL}/test-link"
        }
    )
    return {"message": f"Email task dispatched in {language}!", "task_id": task.id}

if __name__ == "__main__":
    # Allows running the app locally via `python app/main.py`
    uvicorn.run(app, host="0.0.0.0", port=8000)
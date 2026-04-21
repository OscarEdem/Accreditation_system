import logging
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
from app.services.s3 import create_presigned_upload_url, verify_s3_file
from app.api.deps import RateLimiter

router = APIRouter()

logger = logging.getLogger(__name__)

ALLOWED_TYPES = ["image/jpeg", "image/png", "image/webp", "application/pdf"]
PHOTO_MAX_SIZE = 2 * 1024 * 1024  # 2 MB
DOC_MAX_SIZE = 5 * 1024 * 1024    # 5 MB

class PresignedUrlRequest(BaseModel):
    file_name: str
    file_type: str
    file_size: int
    is_photo: bool = False

class PresignedUrlResponse(BaseModel):
    upload_url: str
    upload_fields: dict
    file_key: str
    file_url: str

class ConfirmUploadRequest(BaseModel):
    file_key: str

@router.post("/presigned-url", response_model=PresignedUrlResponse, summary="Get Direct S3 Upload URL", dependencies=[Depends(RateLimiter(requests=60, window=60))])
async def get_presigned_url(
    request: PresignedUrlRequest
):
    """
    Generates a secure, temporary AWS S3 URL so the frontend can upload files directly to the cloud without bottlenecking the backend server.
    
    **Frontend Implementation Workflow (Crucial):**
    1. Call this endpoint with the file's details.
    2. The API returns an `upload_url` and a dictionary of `upload_fields`.
    3. Create a `FormData` object in javascript. Append ALL keys from `upload_fields` first, then append the actual `file` object LAST.
    4. POST the FormData to the `upload_url` (do NOT include your JWT token here, AWS doesn't need it).
    5. If successful (HTTP 204), the file is in S3! Save the returned `file_url` to submit with the final Application payload.
    
    **Example Javascript:**
    ```javascript
    const formData = new FormData();
    Object.entries(response.upload_fields).forEach(([key, value]) => {
      formData.append(key, value);
    });
    formData.append('file', myFileObject); // MUST BE LAST
    
    await fetch(response.upload_url, { method: 'POST', body: formData });
    ```
    """
    max_allowed_size = PHOTO_MAX_SIZE if request.is_photo else DOC_MAX_SIZE

    if request.file_type not in ALLOWED_TYPES:
        raise HTTPException(status_code=400, detail="Unsupported file type. Allowed: JPEG, PNG, WEBP, PDF.")
        
    if request.file_size > max_allowed_size:
        raise HTTPException(status_code=400, detail=f"File too large. Maximum size is {max_allowed_size // (1024 * 1024)}MB.")
        
    logger.info(f"Requested pre-signed S3 URL for {request.file_name}")
    
    url_data = create_presigned_upload_url(file_name=request.file_name, file_type=request.file_type, max_size=max_allowed_size)
    if not url_data:
        raise HTTPException(status_code=500, detail="Could not generate S3 upload URL")
    
    return PresignedUrlResponse(**url_data)

@router.post("/confirm", summary="Verify Successful Upload and File Content", dependencies=[Depends(RateLimiter(requests=60, window=60))])
async def confirm_upload(
    request: ConfirmUploadRequest
):
    """
    After uploading to S3, call this endpoint with the `file_key` to verify:
    1. The file exists in S3
    2. The file's content matches the expected MIME type (prevents polyglot attacks)
    """
    import boto3
    import magic
    from app.config.settings import settings
    s3_client = boto3.client(
        "s3",
        aws_access_key_id=settings.AWS_ACCESS_KEY_ID,
        aws_secret_access_key=settings.AWS_SECRET_ACCESS_KEY,
        region_name=settings.AWS_REGION
    )
    try:
        obj = s3_client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=request.file_key)
        file_content = obj["Body"].read(8192)  # Read first 8KB
        detected_type = magic.from_buffer(file_content, mime=True)
    except Exception as e:
        logger.error(f"S3 file verification failed: {e}")
        raise HTTPException(status_code=404, detail="File not found in S3. Upload may have failed.")

    # Determine expected type from file extension
    ext = request.file_key.split(".")[-1].lower()
    expected_types = {
        "jpg": "image/jpeg",
        "jpeg": "image/jpeg",
        "png": "image/png",
        "webp": "image/webp",
        "pdf": "application/pdf"
    }
    expected_type = expected_types.get(ext)
    if not expected_type or detected_type != expected_type:
        logger.warning(f"File type mismatch: expected {expected_type}, got {detected_type}")
        # Optionally, delete the file if invalid
        s3_client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=request.file_key)
        raise HTTPException(status_code=400, detail=f"File content does not match expected type. Detected: {detected_type}")

    return {"status": "confirmed", "file_key": request.file_key, "mime_type": detected_type}